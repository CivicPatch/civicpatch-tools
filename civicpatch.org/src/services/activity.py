import logging

from core.activity import field_changes
from core.jurisdiction_patch import JurisdictionPatch
from core.people_diff import diff_people
from database import posts
from database.activity import create_activity_row, create_activity_rows
from database.database import get_pool
from schemas.assertions import EntityType
from schemas.activity import Change, PersonChange
from shared.schemas import POST_FIELD
from shared.utils.statuses import ActivityType

logger = logging.getLogger(__name__)


async def diff_manual_edits(before: list[dict], after: list[dict]) -> list[PersonChange]:
    """The reviewer's manual edits, as typed changes — split out of `record_manual_edits` so a
    caller can inspect the diff before deciding how to record it (see `edit_published`, which
    folds a single change onto its own publish row instead of writing it here)."""
    labels = await _post_labels(before + after)
    return diff_people(before, after, labels)


async def write_person_changes(
    changeset_id: str,
    jurisdiction_ocdid: str,
    user_id: str,
    changes: list[PersonChange],
) -> None:
    """Best-effort, like the event records above: callers use this after their own write has
    already succeeded, so a logging failure must not surface as one."""
    try:
        await create_activity_rows(
            [(change.type, change.payload) for change in changes],
            user_id,
            jurisdiction_ocdid,
            changeset_id,
        )
    except Exception:
        logger.exception("Failed to record manual edits for request %s", changeset_id)


async def record_manual_edits(
    changeset_id: str,
    jurisdiction_ocdid: str,
    user_id: str,
    before: list[dict],
    after: list[dict],
) -> None:
    # The diff is the reviewer's manual edits: the PR's contents before this publish
    # versus the content just written to GitHub. Best-effort, like the event records above.
    try:
        changes = await diff_manual_edits(before, after)
    except Exception:
        logger.exception("Failed to record manual edits for request %s", changeset_id)
        return
    await write_person_changes(changeset_id, jurisdiction_ocdid, user_id, changes)


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
    # Best-effort: the PR is already open, so a logging failure must not surface as one.
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


async def _post_labels(people: list[dict]) -> dict[str, str]:
    """`post_id` → the post's label, for the feed.

    Resolved at write time rather than read time: the log is append-only, so it should say what
    the change meant when it was made — a post renamed later does not rewrite history. Without
    it the feed prints the uuid, which is what kept `post_id` out of `EDITABLE_FIELDS`.
    """
    post_ids = [
        post_id
        for post_id in {person.get(POST_FIELD) for person in people}
        if isinstance(post_id, str)
    ]
    if not post_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await posts.get_many(cur, post_ids)
    return {post_id: row.label for post_id, row in found.items() if row.label}
