import logging

from core.change_log_diff import diff_people
from database.change_logs import create_change_log
from database.requests import get_request_jurisdiction
from schemas.change_logs import FieldChange, JurisdictionChangePayload
from shared.utils.statuses import ChangeLogType

logger = logging.getLogger(__name__)


async def record_publish(request_id: str, user_id: str | None) -> None:
    # Best-effort: the publish already succeeded, so a logging failure must not surface as one.
    try:
        jurisdiction_ocdid = await get_request_jurisdiction(request_id)
        await create_change_log(ChangeLogType.MERGE_REVIEW, user_id, jurisdiction_ocdid, request_id)
    except Exception:
        logger.exception("Failed to record merge_review change log for request %s", request_id)


async def record_close(request_id: str, user_id: str | None) -> None:
    # Best-effort: the close already succeeded, so a logging failure must not surface as one.
    try:
        jurisdiction_ocdid = await get_request_jurisdiction(request_id)
        await create_change_log(ChangeLogType.CLOSE_REVIEW, user_id, jurisdiction_ocdid, request_id)
    except Exception:
        logger.exception("Failed to record close_review change log for request %s", request_id)


async def record_manual_edits(
    request_id: str,
    jurisdiction_ocdid: str,
    user_id: str,
    before: list[dict],
    after: list[dict],
) -> None:
    # The diff is the reviewer's manual edits: the PR's contents before this publish
    # versus the content just written to GitHub. Best-effort, like the event records above.
    try:
        for change in diff_people(before, after):
            await create_change_log(change.type, user_id, jurisdiction_ocdid, request_id, change.payload)
    except Exception:
        logger.exception("Failed to record manual edits for request %s", request_id)


async def record_jurisdiction_edit(
    request_id: str,
    jurisdiction_ocdid: str,
    jurisdiction_name: str,
    user_id: str,
    before_url: str | None,
    after_url: str | None,
) -> None:
    # Best-effort: the PR is already open, so a logging failure must not surface as one.
    try:
        payload = JurisdictionChangePayload(
            jurisdiction_ocdid=jurisdiction_ocdid,
            jurisdiction_name=jurisdiction_name,
            fields=[FieldChange(field="url", before=before_url, after=after_url)],
        )
        await create_change_log(
            ChangeLogType.EDIT_JURISDICTION, user_id, jurisdiction_ocdid, request_id, payload
        )
    except Exception:
        logger.exception("Failed to record jurisdiction edit for %s", jurisdiction_ocdid)
