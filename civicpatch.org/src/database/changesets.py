import json
import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Optional

from database.change_logs import record_dismissal
from database.database import get_pool
from database.review_sessions import (
    SESSION_IDLE_TIMEOUT_MINUTES,
    ReviewSessionEntryStatus,
)
from shared.utils.statuses import (
    TERMINAL_PIPELINE_RUN_STATUSES,
    ChangesetKind,
    DismissalReason,
    PipelineIssueStatus,
    PipelineIssueType,
    PipelineRunStatus,
    RequestReviewStatus,
)

logger = logging.getLogger(__name__)

# Derived from the two timestamps, never stored; a CHECK forbids both being set.
# Requires the requests table aliased `r`.
REVIEW_STATUS = (
    "CASE "
    f"WHEN r.published_at IS NOT NULL THEN '{RequestReviewStatus.PUBLISHED.value}' "
    f"WHEN r.dismissed_at IS NOT NULL THEN '{RequestReviewStatus.DISMISSED.value}' "
    f"ELSE '{RequestReviewStatus.PENDING.value}' END"
)

# "This jurisdiction already has work in flight" — the scrape-candidate gate. Aliased `r`.
# Errored and cancelled runs leave both timestamps NULL, so they must not count.
WORK_IN_FLIGHT = (
    "r.published_at IS NULL AND r.dismissed_at IS NULL "
    f"AND r.kind != '{ChangesetKind.JURISDICTION_EDIT.value}' "
    f"AND r.status NOT IN ('{PipelineRunStatus.ERROR.value}', "
    f"'{PipelineRunStatus.CANCELLED.value}', '{PipelineRunStatus.RESOLVED.value}') "
    "AND r.status IS NOT NULL"
)

# Why a request left the pool. `dismissed_at` says only that it did.
DISMISSED_SUPERSEDED = "superseded"
DISMISSED_UNCHANGED = "unchanged"

# "A scrape still awaiting human review". Requires the requests table aliased `r`.
#
AVAILABLE_FOR_REVIEW = (
    "EXISTS (SELECT 1 FROM source_records sr WHERE sr.changeset_id = r.id) "
    "AND r.published_at IS NULL AND r.dismissed_at IS NULL "
    f"AND r.kind != '{ChangesetKind.JURISDICTION_EDIT.value}' "
    "AND NOT EXISTS ("
    "SELECT 1 FROM issues i "
    f"WHERE i.issue_type = '{PipelineIssueType.USER_REPORTED.value}' "
    "AND r.id::text = ANY(i.changeset_ids) "
    f"AND i.status NOT IN ('{PipelineIssueStatus.RESOLVED.value}', '{PipelineIssueStatus.SUPERSEDED.value}')"
    ")"
)

# Is the scrape still going? Derived here so no caller needs its own copy of the terminal set.
# `status IS NULL` is a request no pipeline ran — an edit, not something in flight.
RUN_IN_FLIGHT = (
    "r.status IS NOT NULL AND r.status != ALL(ARRAY["
    + ", ".join(f"'{status.value}'" for status in TERMINAL_PIPELINE_RUN_STATUSES)
    + "])"
)

# Request supercede can dismiss.
# Sweep should not dismiss a card still in the queue.
SWEEPABLE = (
    f"{AVAILABLE_FOR_REVIEW} "
    "AND EXISTS ("
    "SELECT 1 FROM jurisdictions j "
    "WHERE j.jurisdiction_ocdid = r.jurisdiction_ocdid "
    "AND j.status = 'active'"
    ")"
)

HELD_BY_REVIEWER = (
    "EXISTS ("
    "SELECT 1 FROM review_session_entries e "
    "WHERE r.id::text = ANY(e.changeset_ids) "
    f"AND (e.status IN ('{ReviewSessionEntryStatus.SAVED}', '{ReviewSessionEntryStatus.RESOLVED}') "
    f"OR (e.status = '{ReviewSessionEntryStatus.CLAIMED}' AND e.created_at >= NOW() - %s))"
    ")"
)


async def register_request_with_pipeline_run(
    changeset_id: str,
    kind: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
    status: PipelineRunStatus = PipelineRunStatus.PENDING,
    progress: int = 0,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (id, kind, jurisdiction_ocdid, arguments_json, created_by_user_id, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                changeset_id,
                kind,
                jurisdiction_ocdid,
                json.dumps(arguments_json),
                created_by_user_id,
            ),
        )

        await conn.execute(
            """
            UPDATE changesets SET status = %s, progress = %s,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, progress, changeset_id),
        )


async def register_request_with_pipeline_run_if_not_exists(
    changeset_id: str,
    kind: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (id, kind, jurisdiction_ocdid, arguments_json, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO NOTHING
            """,
            (changeset_id, kind, jurisdiction_ocdid, json.dumps(arguments_json)),
        )
        await conn.execute(
            """
            UPDATE changesets SET status = %s, progress = %s,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status IS NULL
            """,
            (PipelineRunStatus.PENDING, 0, changeset_id),
        )


async def register_people_edit_request(
    changeset_id: str,
    jurisdiction_ocdid: str,
    created_by_user_id: str,
):
    """A maintainer's hand edit of a live roster. `PEOPLE_EDIT` with a null `status`: nothing ran.

    Born published, and it has to be — the edit writes sightings for anyone added, and those
    would put a pending request straight into the review pool.

    `sourced_at` is now(): the edit is the newest word on the roster and supersedes any older
    pending scrape, which could not be published over it without retiring what the edit added.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (
                id, kind, jurisdiction_ocdid, arguments_json, created_by_user_id,
                published_at, resolved_by_user_id, created_at, sourced_at
            )
            VALUES (%s, %s, %s, '{}'::jsonb, %s, now(), %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                changeset_id,
                ChangesetKind.PEOPLE_EDIT,
                jurisdiction_ocdid,
                created_by_user_id,
                created_by_user_id,
            ),
        )


async def register_sheet_import_request(
    changeset_id: str,
    jurisdiction_ocdid: str,
    created_by_user_id: str,
    batch_id: str,
) -> None:
    """One jurisdiction's worth of a curated-sheet import. `PEOPLE` with a null `status`:
    nothing ran, the same as a hand edit.

    **Unpublished, unlike `register_people_edit_request`.** A hand edit is one person acting on
    a roster they are already looking at, so it is born published; an import proposes a whole
    roster a curator typed elsewhere, and that belongs in the review queue like any other
    proposal. Writing its sightings is what puts it there — `AVAILABLE_FOR_REVIEW` is
    `EXISTS (source_records for this request)`.

    `sourced_at` is now(): a curated sheet is the newest word on the roster, and it is when the
    curator read the source rather than when any machine did.

    `batch_id` says which run made it — so a card can name the import, and the bulk review
    screen can ask `requests` for that batch's current state rather than reading a snapshot.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (
                id, kind, jurisdiction_ocdid, created_by_user_id, batch_id,
                created_at, sourced_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                changeset_id,
                ChangesetKind.SHEET_IMPORT,
                jurisdiction_ocdid,
                created_by_user_id,
                batch_id,
            ),
        )


async def register_jurisdiction_edit_request(
    changeset_id: str,
    jurisdiction_ocdid: str,
    arguments_json: Mapping[str, object],
    open_data_url: str,
    created_by_user_id: Optional[str] = None,
):
    """A hand-edited jurisdiction field. Born published: the edit is already committed."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (
                id, kind, jurisdiction_ocdid, arguments_json, created_by_user_id,
                open_data_url, published_at, resolved_by_user_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, now(), %s, CURRENT_TIMESTAMP)
            """,
            (
                changeset_id,
                ChangesetKind.JURISDICTION_EDIT,
                jurisdiction_ocdid,
                json.dumps(arguments_json),
                created_by_user_id,
                open_data_url,
                created_by_user_id,
            ),
        )


async def get_request_jurisdiction(changeset_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def jurisdictions_for_requests(changeset_ids: list[str]) -> dict[str, str]:
    """Which jurisdiction each request is about. The roster itself is derived from that
    request's sightings, so this is all a caller needs to ask for one."""
    if not changeset_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, jurisdiction_ocdid FROM changesets WHERE id::text = ANY(%s)",
            (changeset_ids,),
        )
        return {changeset_id: ocdid for changeset_id, ocdid in await cur.fetchall()}


async def get_issue_request_details(changeset_ids: list[str]) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.id::text, r.jurisdiction_ocdid, r.arguments_json,
                   COALESCE(j.data->>'name', r.jurisdiction_ocdid) AS jurisdiction_name
            FROM changesets r
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.id::text = ANY(%s)
            ORDER BY r.created_at
            """,
            (changeset_ids,),
        )
        rows = await cur.fetchall()
    return [
        {
            "changeset_id": r[0],
            "jurisdiction_ocdid": r[1],
            "arguments_json": r[2] or {},
            "jurisdiction_name": r[3],
        }
        for r in rows
    ]


async def dismiss_as_unchanged(cur, changeset_id: str) -> bool:
    """Retire a scrape that asserted nothing new. Returns whether it was still open.

    Guarded in the statement rather than by checking first: a reviewer may be publishing this
    very request, and losing that race must not overwrite their decision.
    """
    await cur.execute(
        f"""
        UPDATE changesets
           SET dismissed_at = now(), dismissed_reason = '{DISMISSED_UNCHANGED}'
         WHERE id::text = %s AND published_at IS NULL AND dismissed_at IS NULL
        RETURNING jurisdiction_ocdid
        """,
        (changeset_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return False
    await record_dismissal(cur, changeset_id, row[0], None, DismissalReason.UNCHANGED)
    return True


async def dismiss_superseded_by(
    cur, changeset_id: str, jurisdiction_ocdid: str, sourced_at
) -> list[str]:
    """Dismiss the cards this publish just made pointless, in the publishing transaction.

    `_refuse_if_superseded` makes a stale card unpublishable; this stops it being offered at
    all. The sweep still runs — it catches two *pending* scrapes, which have no publish to hang
    off, and re-checks holds as they expire.
    """
    await cur.execute(
        f"""
        UPDATE changesets
           SET dismissed_at = now(), dismissed_reason = '{DISMISSED_SUPERSEDED}'
         WHERE id IN (
             SELECT r.id FROM changesets r
             WHERE r.jurisdiction_ocdid = %s
               AND r.id::text <> %s
               AND r.sourced_at IS NOT NULL
               AND r.sourced_at < %s
               AND {SWEEPABLE} AND NOT {HELD_BY_REVIEWER}
         )
        RETURNING id::text
        """,
        (
            jurisdiction_ocdid,
            changeset_id,
            sourced_at,
            timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),
        ),
    )
    dismissed = [row[0] for row in await cur.fetchall()]
    # Every jurisdiction here is the one being published into, by construction of the WHERE.
    for changeset_id in dismissed:
        await record_dismissal(
            cur, changeset_id, jurisdiction_ocdid, None, DismissalReason.SUPERSEDED
        )
    return dismissed


async def supersede_stacked_requests() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            -- Ordered by `sourced_at`: which scrape read the source more recently, never
            -- which row was touched more recently. A reviewer editing an old roster did not go
            -- and look again. Work in progress is protected by the held-card exclusion
            -- instead, which is time-boxed on purpose.
            --
            -- `sourced_at IS NOT NULL`, so a request with no run cannot supersede or be
            -- superseded. That is jurisdiction edits (already excluded by `SWEEPABLE`) and,
            -- once it exists, anything typed in rather than scraped.
            WITH candidates AS (
                SELECT r.id, r.jurisdiction_ocdid, r.sourced_at
                FROM changesets r
                WHERE {SWEEPABLE} AND NOT {HELD_BY_REVIEWER}
                  AND r.sourced_at IS NOT NULL
            ),
            -- What can supersede, which is not the same set as what can BE superseded: a
            -- published request is no longer a candidate, so comparing candidates only to each
            -- other left every draft older than a publish in the pool forever.
            --
            -- Built from `candidates`, not re-queried: that inherits the held-card exclusion,
            -- and it must. A reviewer holding the newest card shields the whole jurisdiction
            -- for the pass — sweep the older ones and their rejecting it strands the lot.
            supersedors AS (
                SELECT jurisdiction_ocdid, sourced_at FROM candidates
                UNION ALL
                SELECT r.jurisdiction_ocdid, r.sourced_at
                FROM changesets r
                WHERE r.published_at IS NOT NULL AND r.sourced_at IS NOT NULL
            )
            UPDATE changesets
               SET dismissed_at = now(), dismissed_reason = '{DISMISSED_SUPERSEDED}'
             WHERE id IN (
                 SELECT older.id
                 FROM candidates older
                 WHERE EXISTS (
                     SELECT 1 FROM supersedors newer
                     WHERE newer.jurisdiction_ocdid = older.jurisdiction_ocdid
                       AND newer.sourced_at > older.sourced_at
                 )
             )
            RETURNING id::text, jurisdiction_ocdid
            """,
            (timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),),
        )
        # The sweep spans jurisdictions, so each row carries its own.
        dismissed = await cur.fetchall()
        for changeset_id, jurisdiction_ocdid in dismissed:
            await record_dismissal(
                cur, changeset_id, jurisdiction_ocdid, None, DismissalReason.SUPERSEDED
            )
        return [row[0] for row in dismissed]
