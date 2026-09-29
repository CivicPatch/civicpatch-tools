import logging

from database.activity import create_activity_row, create_activity_rows
from schemas.claims import EntityType
from schemas.activity import Change, PersonChange
from shared.utils.statuses import ActivityType

logger = logging.getLogger(__name__)


async def write_person_changes(
    changeset_id: str,
    jurisdiction_ocdid: str,
    user_id: str,
    changes: list[PersonChange],
) -> None:
    """Best-effort: callers use this after their own write has already succeeded, so a logging
    failure must not surface as one."""
    try:
        await create_activity_rows(
            [(change.type, change.payload) for change in changes],
            user_id,
            jurisdiction_ocdid,
            changeset_id,
        )
    except Exception:
        logger.exception("Failed to record person changes for changeset %s", changeset_id)
