import base64
import logging
from enum import StrEnum

import environment
import httpx
import lib.github.api as github_service
import shared.utils.id_utils as id_utils
from lib.github.auth import get_jurisdictions_sync_headers
from lib.github.pull_requests import PrAuthor, open_attributed_pr
from services.open_data_sync import sync_jurisdictions_by_ocdids
from shared.utils.yaml_utils import yaml_dump, yaml_load

import database.jurisdictions as jurisdictions_db
import database.changesets as changesets_db
import core.jurisdiction_patch as jurisdiction_patch
import services.change_logs as change_logs

logger = logging.getLogger(__name__)


# The only level with a hand-editable registry today; states and counties are upstream-owned.
LOCAL_LEVEL = "local"


class EditRejection(StrEnum):
    """A rejected edit that is the caller's mistake, not a server failure. The value
    doubles as the message shown to them."""

    NO_FIELDS = "No fields to update"
    NO_CHANGES = "No changes to publish"


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
    """The jurisdictions-repo route. Not yet reachable from the app — the live path
    is open_jurisdiction_url_pr — but real code, so it can be exercised by pointing
    JURISDICTIONS_REPO_URL at open-data rather than openstates/jurisdictions.
    """
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
    branch_name = f"civicpatch/jurisdiction-edit/{id_utils.make_changeset_id()}"

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


async def commit_jurisdiction_patch(
    jurisdiction_ocdid: str,
    fields: dict,
    user_id: str | None,
) -> tuple[str | None, str, str]:
    """Patch a jurisdiction's fields and commit them, like editing a person: only what
    was sent is written, and an absent field is left alone rather than cleared.

    Committed directly rather than proposed. A maintainer editing a field has already made
    the decision a pull request exists to carry, and nothing downstream could reject it —
    the PR was auto-merged on the caller's behalf anyway. Removing it makes the edit
    synchronous, which is what retired the reconcile pass that used to answer
    "has it landed yet?".

    The file is read and patched in place, NOT rendered from the database — the opposite of
    how people are published, and deliberately so. civicpatch owns its people; it does not own
    the registry, which od_sync pulls from open-data on a schedule. The file is the source, so
    reading it is reading the truth rather than taking a redundant round trip.

    Measured 2026-08-17, the concrete cost of rendering instead: the real files carry YAML
    comments a full render would delete — 36 in ca/local, 17 in ma/local, 28 in wa/counties,
    9 in wa/state. Fields would survive (the DB stores entries verbatim, `generated_comments`
    and `issues` included); the comments would not.

    Returns (commit_url, url_or_error, changeset_id).
    """
    state = _extract_state(jurisdiction_ocdid)
    file_path = f"data_source/{state}/{LOCAL_LEVEL}/jurisdictions.yml"
    changeset_id = id_utils.make_changeset_id()

    patch = jurisdiction_patch.build_patch(fields)
    if not patch:
        return None, EditRejection.NO_FIELDS, changeset_id

    raw = await github_service.get_github_file_contents(file_path)
    if not raw:
        return None, f"Failed to fetch {file_path}", changeset_id

    # Round-tripped through ruamel so quotes, comments and layout survive: this touches one
    # value in a file listing every jurisdiction in the state.
    doc = yaml_load(raw)
    entry = jurisdiction_patch.find_jurisdiction(doc, jurisdiction_ocdid)
    if entry is None:
        return None, f"Jurisdiction {jurisdiction_ocdid} not found in {file_path}", changeset_id

    before = jurisdiction_patch.current_values(entry, patch)
    if before == patch:
        return None, EditRejection.NO_CHANGES, changeset_id

    changed = ", ".join(sorted(patch))
    commit_url = await github_service.upsert_github_file(
        branch_name=github_service.DEFAULT_BRANCH,
        file_path=file_path,
        content_str=yaml_dump(jurisdiction_patch.apply_patch(doc, jurisdiction_ocdid, patch)),
        commit_message=f"Update {changed}: {jurisdiction_ocdid}",
    )
    if not commit_url:
        return None, f"Failed to commit {file_path}", changeset_id

    # Kept in step so the page reflects the edit immediately. od_sync would bring the same
    # value back from the file on its next run; writing it here removes the wait, and is what
    # replaced the reconcile pass rather than leaving the UI stale until a sync.
    await jurisdictions_db.patch_jurisdiction_entry(jurisdiction_ocdid, patch)

    # Published on commit: there is no review step between the edit and the file, so the
    # request is born resolved rather than waiting for a merge to tell us.
    await changesets_db.register_jurisdiction_edit_request(
        changeset_id=changeset_id,
        jurisdiction_ocdid=jurisdiction_ocdid,
        change_url=commit_url,
        created_by_user_id=user_id,
    )

    # The change log records the url specifically, so it only fires when url moved.
    if user_id:
        await change_logs.record_jurisdiction_edit(
            changeset_id=changeset_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            jurisdiction_name=entry["name"],
            user_id=user_id,
            before=before,
            after=patch,
        )

    return commit_url, commit_url, changeset_id


async def merge_jurisdiction_pr(
    pull_request_number: str, approved_by: str | None, changeset_id: str
) -> None:
    # Best-effort auto-merge: any failure leaves the PR open for a manual merge.
    # open-data, not the jurisdictions repo — that is where the PR was opened.
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
            return
    except Exception:
        logger.exception("Failed to auto-merge jurisdiction PR %s", pull_request_number)
        return

    # Sync the jurisdiction it just changed. Called directly rather than through a status
    # write: this path merged the PR, so it already knows. A failure here is not a merge
    # failure — the merge stands and the hourly od_sync is the backstop.
    try:
        jurisdiction_ocdid = await changesets_db.get_request_jurisdiction(changeset_id)
        if jurisdiction_ocdid:
            await sync_jurisdictions_by_ocdids([jurisdiction_ocdid])
    except Exception:
        logger.exception(
            "Merged jurisdiction PR %s but recording/syncing it failed for request %s; "
            "the hourly od_sync will pick it up",
            pull_request_number,
            changeset_id,
        )
