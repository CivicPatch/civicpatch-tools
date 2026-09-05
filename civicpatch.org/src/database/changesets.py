import json
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Optional

from database.change_logs import record_dismissal
from core.changeset_lifecycle import states_accepting_dismissal
from database.database import get_pool, to_iso
from database.review_sessions import (
    SESSION_IDLE_TIMEOUT_MINUTES,
    ReviewSessionEntryStatus,
)
from database.users import SYSTEM_USER_ID
from shared.utils.id_utils import make_id
from schemas.common import InFlightEntry, InFlightEntryType, JurisdictionInFlight
from shared.utils.statuses import (
    ChangesetKind,
    DismissalReason,
    PipelineIssueStatus,
    PipelineIssueType,
    PipelineRunStatus,
    RequestReviewStatus,
)

logger = logging.getLogger(__name__)

# Derived from the two timestamps, never stored; a CHECK forbids both being set.
# Unaliased, per CLAUDE.md: a fragment that demands its caller alias a table is a runtime
# error waiting, never a typecheck one. `r` was the initial of `requests`, pre-migration-152.
REVIEW_STATUS = (
    "CASE "
    f"WHEN changesets.published_at IS NOT NULL THEN '{RequestReviewStatus.PUBLISHED.value}' "
    f"WHEN changesets.dismissed_at IS NOT NULL THEN '{RequestReviewStatus.DISMISSED.value}' "
    f"ELSE '{RequestReviewStatus.PENDING.value}' END"
)

WORK_IN_FLIGHT = (
    "changesets.published_at IS NULL AND changesets.dismissed_at IS NULL "
    f"AND changesets.kind != '{ChangesetKind.JURISDICTION_EDIT.value}'"
)

# Duplicates `DismissalReason`; kept only because the SQL fragments below splice it.
DISMISSED_SUPERSEDED = "superseded"

# A scrape still awaiting human review. Unaliased; callers use `FROM changesets` bare.
AVAILABLE_FOR_REVIEW = (
    "EXISTS (SELECT 1 FROM source_records sr WHERE sr.changeset_id = changesets.id) "
    # Composed, not restated: widening one used to leave the two disagreeing.
    f"AND {WORK_IN_FLIGHT} "
    "AND NOT EXISTS ("
    "SELECT 1 FROM issues i "
    f"WHERE i.issue_type = '{PipelineIssueType.USER_REPORTED.value}' "
    "AND changesets.id::text = ANY(i.changeset_ids) "
    f"AND i.status NOT IN ('{PipelineIssueStatus.RESOLVED.value}', '{PipelineIssueStatus.SUPERSEDED.value}')"
    ")"
)

# The run behind a changeset. No run — an import or a hand edit — answers NULL.
RUN_IN_FLIGHT = (
    "EXISTS (SELECT 1 FROM pipeline_runs "
    "WHERE pipeline_runs.changeset_id = changesets.id AND pipeline_runs.finished_at IS NULL)"
)
RUN_STATUS = (
    "(SELECT status FROM pipeline_runs WHERE pipeline_runs.changeset_id = changesets.id)"
)
RUN_PROGRESS = (
    "(SELECT progress FROM pipeline_runs WHERE pipeline_runs.changeset_id = changesets.id)"
)

# Request supercede can dismiss.
# Sweep should not dismiss a card still in the queue.
SWEEPABLE = (
    f"{AVAILABLE_FOR_REVIEW} "
    "AND EXISTS ("
    "SELECT 1 FROM jurisdictions j "
    "WHERE j.jurisdiction_ocdid = changesets.jurisdiction_ocdid "
    "AND j.status = 'active'"
    ")"
)

HELD_BY_REVIEWER = (
    "EXISTS ("
    "SELECT 1 FROM review_session_entries e "
    "WHERE changesets.id::text = ANY(e.changeset_ids) "
    f"AND (e.status IN ('{ReviewSessionEntryStatus.SAVED}', '{ReviewSessionEntryStatus.RESOLVED}') "
    f"OR (e.status = '{ReviewSessionEntryStatus.CLAIMED}' AND e.created_at >= NOW() - %s))"
    ")"
)


async def register_scrape_changeset(run_id: str) -> str:
    """Mint the proposal a successful run produced, and link the run to it.

    Only called from ingest, and only on success — a run that proposed nothing has no changeset,
    which is what makes `changesets.changeset_state` a question about a proposal, not an attempt.

    `created_at` is now(): the roster came into being when the scrape reported it.
    """
    changeset_id = make_id()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changesets (
                id, kind, jurisdiction_ocdid, created_by_user_id,
                created_at, updated_at
            )
            SELECT %s, %s, run.jurisdiction_ocdid, run.created_by_user_id,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM pipeline_runs run WHERE run.id = %s
            """,
            (changeset_id, ChangesetKind.SCRAPE, run_id),
        )
        await cur.execute(
            "UPDATE pipeline_runs SET changeset_id = %s WHERE id = %s",
            (changeset_id, run_id),
        )
        await conn.commit()
    return changeset_id


async def register_people_edit_request(
    changeset_id: str,
    jurisdiction_ocdid: str,
    created_by_user_id: str,
):
    """A maintainer's hand edit of a live roster. Nothing ran, so no run.

    Born published: the edit writes sightings for anyone added, and a pending changeset holding
    those would land straight in the review pool.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (
                id, kind, jurisdiction_ocdid, created_by_user_id,
                published_at, resolved_by_user_id, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, now(), %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
    """One jurisdiction's worth of a curated-sheet import. Nothing ran, so no run.

    Unpublished, unlike a hand edit: an import proposes a whole roster typed elsewhere, so it
    belongs in the review queue. Writing its sightings is what puts it there.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (
                id, kind, jurisdiction_ocdid, created_by_user_id, batch_id,
                created_at, updated_at
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
    change_url: str,
    created_by_user_id: Optional[str] = None,
):
    """A hand-edited jurisdiction field. Born published: the edit is already committed."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO changesets (
                id, kind, jurisdiction_ocdid, created_by_user_id,
                change_url, published_at, resolved_by_user_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, now(), %s, CURRENT_TIMESTAMP)
            """,
            (
                changeset_id,
                ChangesetKind.JURISDICTION_EDIT,
                jurisdiction_ocdid,
                created_by_user_id,
                change_url,
                created_by_user_id,
            ),
        )


async def live_roster_changeset(cur, jurisdiction_ocdid: str) -> str | None:
    """The changeset whose publish produced the live roster — not the one in flight."""
    await cur.execute(
        """
        SELECT id::text FROM changesets
        WHERE jurisdiction_ocdid = %s AND published_at IS NOT NULL
        ORDER BY published_at DESC
        LIMIT 1
        """,
        (jurisdiction_ocdid,),
    )
    row = await cur.fetchone()
    return row[0] if row else None


# Two lanes, rooted apart: before ingest there is no changeset row to reach a run through. They
# split on `changeset_id`, so a run that has minted one is reported by the changeset lane.
IN_FLIGHT_SQL = f"""
    SELECT id::text, '{InFlightEntryType.PIPELINE_RUN.value}' AS entry_type,
           created_at, updated_at,
           '{ChangesetKind.SCRAPE.value}' AS kind, NULL AS change_url, status, progress,
           true AS is_running, false AS awaiting_review
    FROM pipeline_runs
    WHERE jurisdiction_ocdid = %s
      AND finished_at IS NULL
      AND changeset_id IS NULL

    UNION ALL

    SELECT id::text, '{InFlightEntryType.CHANGESET.value}' AS entry_type,
           created_at, updated_at, kind, change_url, status, progress,
           is_running, awaiting_review
    FROM (
        SELECT changesets.id, changesets.created_at, changesets.updated_at, changesets.kind, changesets.change_url,
               {RUN_STATUS} AS status, {RUN_PROGRESS} AS progress,
               {RUN_IN_FLIGHT} AS is_running,
               {AVAILABLE_FOR_REVIEW} AS awaiting_review
        FROM changesets
        WHERE changesets.jurisdiction_ocdid = %s
          AND changesets.published_at IS NULL
          AND changesets.dismissed_at IS NULL
    ) flags
    WHERE is_running OR awaiting_review

    ORDER BY created_at DESC
"""


async def get_in_flight(jurisdiction_ocdid: str) -> JurisdictionInFlight:
    """What this jurisdiction is still waiting on, without reading its whole history."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(IN_FLIGHT_SQL, (jurisdiction_ocdid, jurisdiction_ocdid))
        in_flight = [
            InFlightEntry(
                id=row[0],
                entry_type=row[1],
                created_at=to_iso(row[2]),
                updated_at=to_iso(row[3]),
                kind=row[4],
                change_url=row[5],
                pipeline_run_status=row[6],
                pipeline_run_progress=row[7],
                is_running=row[8],
                awaiting_review=row[9],
            )
            for row in await cur.fetchall()
        ]

        # `max(published_at)`, not the newest row's: a changeset published today may have been
        # scraped before one published last week.
        await cur.execute(
            """
            SELECT max(published_at), count(*)
            FROM changesets WHERE jurisdiction_ocdid = %s
            """,
            (jurisdiction_ocdid,),
        )
        totals = await cur.fetchone()
        last_published_at, total = totals if totals else (None, 0)

    return JurisdictionInFlight(
        in_flight=in_flight,
        last_published_at=to_iso(last_published_at),
        total_changesets=total,
    )


async def live_roster_changeset_for(jurisdiction_ocdid: str) -> str | None:
    """`live_roster_changeset` for a caller that holds no cursor."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await live_roster_changeset(cur, jurisdiction_ocdid)


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


async def organizations_for_changesets(changeset_ids: list[str]) -> dict[str, str]:
    """Which organization each changeset is about, for the ones that name it.

    A changeset with none is a jurisdiction that has never published, so it has no posts either
    and the caller's lookup would find nothing regardless — hence absent rather than null.
    """
    if not changeset_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, organization_id::text FROM changesets
            WHERE id::text = ANY(%s) AND organization_id IS NOT NULL
            """,
            (changeset_ids,),
        )
        return {changeset_id: org for changeset_id, org in await cur.fetchall()}


async def get_issue_request_details(changeset_ids: list[str]) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT changesets.id::text, changesets.jurisdiction_ocdid, run.arguments_json,
                   COALESCE(j.data->>'name', changesets.jurisdiction_ocdid) AS jurisdiction_name
            FROM changesets
            LEFT JOIN pipeline_runs run ON run.changeset_id = changesets.id
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = changesets.jurisdiction_ocdid
            WHERE changesets.id::text = ANY(%s)
            ORDER BY changesets.created_at
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


# Which rows are in which state, in SQL. The Python side of this is
# `core.changeset_lifecycle`; this is the same fact where the UPDATE can use it.
# "This changeset's run, if it had one, finished with a roster." One definition, because both
# halves of the lifecycle guard need it: a dismissal reason may only leave certain states, and
# `publications._refuse_if_not_publishable` asks the same question from the other side.
async def mark_dismissed(
    cur,
    changeset_ids: list[str],
    reason: DismissalReason,
    resolved_by_user_id: str | None = None,
) -> list[tuple[str, str]]:
    """The one writer for a dismissal. Returns the (id, jurisdiction) pairs that transitioned.

    Guarded in the statement, not by reading first: a reviewer may be publishing this very
    changeset, and losing that race must not overwrite their decision.

    One guard, since a changeset is only minted by a run that succeeded — there is no longer a
    failed-run changeset to keep a person from mislabelling.
    """
    if not changeset_ids:
        return []
    # The machine decides which states this dismissal may leave; the statement applies it.
    # `changesets.changeset_state` is the generated column, so this is one atomic read-and-write —
    # first, so nothing can lose the race to a concurrent publish.
    await cur.execute(
        """
        UPDATE changesets
           SET dismissed_at = now(),
               dismissed_reason = %s,
               resolved_by_user_id = COALESCE(%s, resolved_by_user_id, %s)
         WHERE changesets.id::text = ANY(%s)
           AND changesets.changeset_state = ANY(%s)
        RETURNING changesets.id::text, changesets.jurisdiction_ocdid
        """,
        (
            reason,
            resolved_by_user_id,
            SYSTEM_USER_ID,
            changeset_ids,
            list(states_accepting_dismissal(reason)),
        ),
    )
    dismissed = await cur.fetchall()
    for changeset_id, jurisdiction_ocdid in dismissed:
        await record_dismissal(
            cur, changeset_id, jurisdiction_ocdid, resolved_by_user_id, reason
        )
    return [(row[0], row[1]) for row in dismissed]


async def dismiss_superseded_by(
    cur, changeset_id: str, jurisdiction_ocdid: str, updated_at
) -> list[str]:
    """Dismiss the cards this publish just made pointless, in the publishing transaction.

    `_refuse_if_superseded` makes a stale card unpublishable; this stops it being offered at
    all. The sweep still runs — it catches two *pending* scrapes, which have no publish to hang
    off, and re-checks holds as they expire.
    """
    # Selection here, marking in `mark_dismissed`. Splitting them is safe inside this
    # transaction because that UPDATE re-checks the same guards, so a row a reviewer takes
    # between the two statements is skipped rather than overwritten.
    await cur.execute(
        f"""
        SELECT changesets.id::text FROM changesets
         WHERE changesets.jurisdiction_ocdid = %s
           AND changesets.id::text <> %s
           AND changesets.updated_at IS NOT NULL
           AND changesets.updated_at < %s
           AND {SWEEPABLE} AND NOT {HELD_BY_REVIEWER}
        """,
        (
            jurisdiction_ocdid,
            changeset_id,
            updated_at,
            timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),
        ),
    )
    stale = [row[0] for row in await cur.fetchall()]
    dismissed = await mark_dismissed(cur, stale, DismissalReason.SUPERSEDED)
    return [row[0] for row in dismissed]


async def supersede_stacked_requests() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            WITH candidates AS (
                SELECT changesets.id, changesets.jurisdiction_ocdid, changesets.updated_at
                FROM changesets
                WHERE {SWEEPABLE} AND NOT {HELD_BY_REVIEWER}
                  AND changesets.updated_at IS NOT NULL
            ),
            supersedors AS (
                SELECT jurisdiction_ocdid, updated_at FROM candidates
                UNION ALL
                SELECT changesets.jurisdiction_ocdid, changesets.updated_at
                FROM changesets
                WHERE changesets.published_at IS NOT NULL AND changesets.updated_at IS NOT NULL
            )
            SELECT older.id::text
              FROM candidates older
             WHERE EXISTS (
                 SELECT 1 FROM supersedors newer
                 WHERE newer.jurisdiction_ocdid = older.jurisdiction_ocdid
                   AND newer.updated_at > older.updated_at
             )
            """,
            (timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),),
        )
        stale = [row[0] for row in await cur.fetchall()]
        dismissed = await mark_dismissed(cur, stale, DismissalReason.SUPERSEDED)
        await conn.commit()
        return [row[0] for row in dismissed]


async def get_updated_at(cur, changeset_id: str) -> datetime:
    """When this changeset's content was last confirmed. Every kind has one; only a scrape
    has a run."""
    await cur.execute(
        "SELECT updated_at FROM changesets WHERE id::text = %s",
        (changeset_id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise ValueError(f"No changeset {changeset_id}")
    return row[0]
