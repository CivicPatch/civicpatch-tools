import base64
import logging

import environment
import httpx
import lib.github.api as github_service
import shared.utils.id_utils as id_utils
from lib.github.auth import get_jurisdictions_sync_headers
from lib.github.pull_requests import PrAuthor, open_attributed_pr
from shared.utils.yaml_utils import yaml_dump, yaml_load

import database.requests as requests_db
import services.change_logs as change_logs
import services.pull_request_sync as pull_request_sync
from shared.utils.statuses import PullRequestStatus, SourceRepo

logger = logging.getLogger(__name__)


def _get_jurisdictions_repo_url() -> str:
    return environment.get_env_vars()["JURISDICTIONS_REPO_URL"]


def _extract_state(jurisdiction_ocdid: str) -> str:
    for part in jurisdiction_ocdid.split("/"):
        if part.startswith("state:"):
            return part.split(":")[1]
    raise ValueError(f"Cannot extract state from: {jurisdiction_ocdid}")


def _apply_fields(entry: dict, fields: dict) -> None:
    for key in ("url", "population", "geoid"):
        if fields.get(key) is not None:
            entry[key] = fields[key]


async def open_jurisdiction_edit_pr(
    jurisdiction_ocdid: str,
    fields: dict,
    author: PrAuthor,
) -> tuple[int, str] | tuple[None, str]:
    repo_url = _get_jurisdictions_repo_url()
    state = _extract_state(jurisdiction_ocdid)
    file_path = f"data/{state}/local/jurisdictions.yml"

    auth_headers = await get_jurisdictions_sync_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{repo_url}/contents/{file_path}",
            headers=auth_headers,
        )
    if response.status_code == 404:
        entries = [{"id": jurisdiction_ocdid}]
        _apply_fields(entries[0], fields)
    elif response.status_code != 200:
        return (
            None,
            f"Failed to fetch {file_path}: {response.json().get('message', 'unknown')}",
        )
    else:
        raw = base64.b64decode(response.json()["content"]).decode("utf-8")
        entries = yaml_load(raw)

        updated = False
        for entry in entries:
            if entry.get("id") == jurisdiction_ocdid:
                _apply_fields(entry, fields)
                updated = True
                break

        if not updated:
            return None, f"Jurisdiction {jurisdiction_ocdid} not found in {file_path}"

    content_str = yaml_dump(entries)
    branch_name = f"civicpatch/jurisdiction-edit/{id_utils.make_request_id()}"

    return await open_attributed_pr(
        branch_name=branch_name,
        file_path=file_path,
        content=content_str,
        commit_message=f"Update metadata: {jurisdiction_ocdid}",
        pull_request_title=f"Jurisdiction edit: {state}/{jurisdiction_ocdid.split('/')[-2]}",
        pull_request_body=f"Updating metadata for `{jurisdiction_ocdid}`.",
        author=author,
        repo_url=repo_url,
        headers=auth_headers,
    )


def _find_jurisdiction(doc: dict, jurisdiction_ocdid: str) -> dict | None:
    for entry in doc.get("jurisdictions", []):
        if entry.get("id") == jurisdiction_ocdid:
            return entry
    return None


async def open_jurisdiction_url_pr(
    jurisdiction_ocdid: str,
    url: str | None,
    author: PrAuthor,
    user_id: str | None,
) -> tuple[int | None, str, str]:
    """Returns (pull_request_number, url_or_error, request_id)."""
    state = _extract_state(jurisdiction_ocdid)
    file_path = f"data_source/{state}/local/jurisdictions.yml"

    request_id = id_utils.make_request_id()

    raw = await github_service.get_github_file_contents(file_path)
    if not raw:
        return None, f"Failed to fetch {file_path}", request_id

    doc = yaml_load(raw)
    entry = _find_jurisdiction(doc, jurisdiction_ocdid)
    if entry is None:
        return (
            None,
            f"Jurisdiction {jurisdiction_ocdid} not found in {file_path}",
            request_id,
        )

    before_url = entry.get("url")
    entry["url"] = url

    branch_name = f"civicpatch/jurisdiction-edit/{request_id}"
    result = await open_attributed_pr(
        branch_name=branch_name,
        file_path=file_path,
        content=yaml_dump(doc),
        commit_message=f"Update url: {jurisdiction_ocdid}",
        pull_request_title=f"Jurisdiction url edit: {state}/{jurisdiction_ocdid.split('/')[-2]}",
        pull_request_body=f"Updating url for `{jurisdiction_ocdid}`.",
        author=author,
    )

    pull_request_number, url_or_error = result
    if pull_request_number is None:
        return None, url_or_error, request_id

    # Tracked like any other PR so its state can be synced and surfaced. No
    # pipeline_run: nothing ran.
    await requests_db.register_jurisdiction_edit_request(
        request_id=request_id,
        jurisdiction_ocdid=jurisdiction_ocdid,
        arguments_json={"url": url},
        pr_number=pull_request_number,
        pr_url=url_or_error,
        requested_by_user_id=user_id,
    )

    if user_id and before_url != url:
        await change_logs.record_jurisdiction_edit(
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            jurisdiction_name=entry["name"],
            user_id=user_id,
            before_url=before_url,
            after_url=url,
        )

    return pull_request_number, url_or_error, request_id


async def merge_jurisdiction_pr(
    pull_request_number: str, approved_by: str | None, request_id: str
) -> None:
    # Best-effort auto-merge: any failure leaves the PR open for a manual merge.
    #
    # Every call names the jurisdictions repo. A pr_number only means something
    # inside its own repo, and these helpers default to open-data.
    try:
        mergeable_state = await github_service.get_pull_request_mergeability(
            pull_request_number, source_repo=SourceRepo.JURISDICTIONS
        )
        if mergeable_state != "clean":
            logger.warning(
                "Jurisdiction PR %s not mergeable (%s); leaving open",
                pull_request_number,
                mergeable_state,
            )
            return
        merge_error = await github_service.merge_pull_request(
            pull_request_number,
            approved_by=approved_by,
            source_repo=SourceRepo.JURISDICTIONS,
        )
        if merge_error:
            logger.warning(
                "Jurisdiction PR %s merge failed: %s", pull_request_number, merge_error
            )
            return
    except Exception:
        logger.exception("Failed to auto-merge jurisdiction PR %s", pull_request_number)
        return

    # Record the merge and run its side effects through the same path every other PR
    # uses, so the row's status is right and the targeted sync fires. A failure here
    # is not a merge failure: the merge stands and the hourly od_sync is the backstop.
    try:
        await pull_request_sync.apply_pull_request_status(
            request_id, PullRequestStatus.MERGED
        )
    except Exception:
        logger.exception(
            "Merged jurisdiction PR %s but recording/syncing it failed for request %s; "
            "the hourly od_sync will pick it up",
            pull_request_number,
            request_id,
        )
