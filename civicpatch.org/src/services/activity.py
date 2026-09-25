import logging

from core.activity import field_changes
from core.jurisdiction_patch import JurisdictionPatch
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


async def record_jurisdiction_edit(
    changeset_id: str,
    jurisdiction_ocdid: str,
    jurisdiction_name: str,
    user_id: str,
    before: JurisdictionPatch,
    after: JurisdictionPatch,
) -> None:
    """`before` names the fields the edit was scoped to, so the diff covers all of them —
    every other field used to go unrecorded because only `url` was passed."""
    try:
        payload = Change(
            entity_type=EntityType.JURISDICTION,
            entity_id=jurisdiction_ocdid,
            subject=jurisdiction_name,
            fields=field_changes(before, after),
        )
        await create_activity_row(
            ActivityType.EDIT_JURISDICTION, user_id, jurisdiction_ocdid, changeset_id, payload
        )
    except Exception:
        logger.exception("Failed to record jurisdiction edit for %s", jurisdiction_ocdid)
