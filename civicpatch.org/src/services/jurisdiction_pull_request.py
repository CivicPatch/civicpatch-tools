import base64
import logging

import environment
import httpx
import lib.github.api as github_service
import shared.utils.id_utils as id_utils
from lib.github.auth import get_jurisdictions_sync_headers
from lib.github.pull_requests import PrAuthor, open_attributed_pr
from shared.utils.yaml_utils import yaml_dump, yaml_load

import services.change_logs as change_logs

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
) -> tuple[int, str] | tuple[None, str]:
    state = _extract_state(jurisdiction_ocdid)
    file_path = f"data_source/{state}/local/jurisdictions.yml"

    raw = await github_service.get_github_file_contents(file_path)
    if not raw:
        return None, f"Failed to fetch {file_path}"

    doc = yaml_load(raw)
    entry = _find_jurisdiction(doc, jurisdiction_ocdid)
    if entry is None:
        return None, f"Jurisdiction {jurisdiction_ocdid} not found in {file_path}"

    before_url = entry.get("url")
    entry["url"] = url

    request_id = id_utils.make_request_id()
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

    if result[0] is not None and user_id and before_url != url:
        await change_logs.record_jurisdiction_edit(
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            jurisdiction_name=entry["name"],
            user_id=user_id,
            before_url=before_url,
            after_url=url,
        )

    return result


async def merge_jurisdiction_pr(
    pull_request_number: str, approved_by: str | None
) -> None:
    # Best-effort auto-merge: any failure leaves the PR open for a manual merge.
    try:
        mergeable_state = await github_service.get_pull_request_mergeability(
            pull_request_number
        )
        if mergeable_state != "clean":
            logger.warning(
                "Jurisdiction PR %s not mergeable (%s); leaving open",
                pull_request_number,
                mergeable_state,
            )
            return
        merge_error = await github_service.merge_pull_request(
            pull_request_number, approved_by=approved_by
        )
        if merge_error:
            logger.warning(
                "Jurisdiction PR %s merge failed: %s", pull_request_number, merge_error
            )
    except Exception:
        logger.exception("Failed to auto-merge jurisdiction PR %s", pull_request_number)
