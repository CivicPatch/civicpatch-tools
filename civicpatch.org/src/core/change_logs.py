import logging

from core.change_log_diff import diff_people
from database.change_logs import create_change_log
from database.people import get_people_data_by_request_ids
from database.requests import get_request_jurisdiction
from shared.utils.statuses import ChangeLogType

logger = logging.getLogger(__name__)


async def record_merge_review(request_id: str, user_id: str) -> None:
    # Best-effort: the merge already succeeded, so a logging failure must not surface as one.
    try:
        jurisdiction_ocdid = await get_request_jurisdiction(request_id)
        if jurisdiction_ocdid is None:
            logger.warning("No jurisdiction for request %s; skipping merge_review change log", request_id)
            return
        data = await get_people_data_by_request_ids([jurisdiction_ocdid], [request_id], view="detail")
        entry = data.get(request_id, {})
        await create_change_log(ChangeLogType.MERGE_REVIEW, user_id, jurisdiction_ocdid, request_id)
        for change in diff_people(entry.get("existing", []), entry.get("proposed", [])):
            await create_change_log(change.type, user_id, jurisdiction_ocdid, request_id, change.payload)
    except Exception:
        logger.exception("Failed to record merge_review change log for request %s", request_id)


async def record_close_review(request_id: str, user_id: str | None) -> None:
    # Best-effort: the close already succeeded, so a logging failure must not surface as one.
    try:
        jurisdiction_ocdid = await get_request_jurisdiction(request_id)
        await create_change_log(ChangeLogType.CLOSE_REVIEW, user_id, jurisdiction_ocdid, request_id)
    except Exception:
        logger.exception("Failed to record close_review change log for request %s", request_id)
