import json
from datetime import timedelta
from typing import Optional

from database.database import get_pool
from database.review_sessions import (
    SESSION_IDLE_TIMEOUT_MINUTES,
    ReviewSessionEntryStatus,
)
from shared.utils.statuses import (
    TERMINAL_PIPELINE_RUN_STATUSES,
    PipelineIssueStatus,
    PipelineIssueType,
    PipelineRunStatus,
    RequestReviewStatus,
    RequestType,
)

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
    f"AND r.request_type != '{RequestType.JURISDICTION_MANUAL_EDIT.value}' "
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
    "EXISTS (SELECT 1 FROM source_records sr WHERE sr.request_id = r.id) "
    "AND r.published_at IS NULL AND r.dismissed_at IS NULL "
    f"AND r.request_type != '{RequestType.JURISDICTION_MANUAL_EDIT.value}' "
    "AND NOT EXISTS ("
    "SELECT 1 FROM issues i "
    f"WHERE i.issue_type = '{PipelineIssueType.USER_REPORTED.value}' "
    "AND r.id::text = ANY(i.request_ids) "
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
    "WHERE r.id::text = ANY(e.request_ids) "
    f"AND (e.status IN ('{ReviewSessionEntryStatus.SAVED}', '{ReviewSessionEntryStatus.RESOLVED}') "
    f"OR (e.status = '{ReviewSessionEntryStatus.CLAIMED}' AND e.created_at >= NOW() - %s))"
    ")"
)


async def register_request_with_pipeline_run(
    request_id: str,
    job_type: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
    requested_by_user_id: Optional[str] = None,
    status: PipelineRunStatus = PipelineRunStatus.PENDING,
    progress: int = 0,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, requested_by_user_id, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (
                request_id,
                job_type,
                jurisdiction_ocdid,
                json.dumps(arguments_json),
                requested_by_user_id,
            ),
        )

        await conn.execute(
            """
            UPDATE requests SET status = %s, progress = %s,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, progress, request_id),
        )


async def register_request_with_pipeline_run_if_not_exists(
    request_id: str,
    job_type: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO NOTHING
            """,
            (request_id, job_type, jurisdiction_ocdid, json.dumps(arguments_json)),
        )
        await conn.execute(
            """
            UPDATE requests SET status = %s, progress = %s,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status IS NULL
            """,
            (PipelineRunStatus.PENDING, 0, request_id),
        )


async def register_foreign_request(
    request_id: str,
    jurisdiction_ocdid: str,
    pr_url: Optional[str],
    provider: str,
):
    """
    Create a request + pull_request record for a PR that has no backing job worker.
    The request_id is "foreign" — derived from the git branch name, not our job pipeline.
    Used by the GitHub webhook handler and hourly PR sync.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, created_at)
            VALUES (%s, 'people', %s, CURRENT_TIMESTAMP)
            """,
            (request_id, jurisdiction_ocdid),
        )

        # No pipeline ran — the id comes off a git branch. SUCCESS because the work is done
        # elsewhere.
        await conn.execute(
            """
            UPDATE requests SET status = %s, progress = 100,
                                sourced_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (PipelineRunStatus.SUCCESS, request_id),
        )



async def register_people_edit_request(
    request_id: str,
    jurisdiction_ocdid: str,
    requested_by_user_id: str,
):
    """A maintainer's hand edit of a live roster. `PEOPLE` with a null `status`: nothing ran.

    Born published, and it has to be — the edit writes sightings for anyone added, and those
    would put a pending request straight into the review pool.

    `sourced_at` is now(): the edit is the newest word on the roster and supersedes any older
    pending scrape, which could not be published over it without retiring what the edit added.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (
                id, request_type, jurisdiction_ocdid, arguments_json, requested_by_user_id,
                published_at, resolved_by_user_id, created_at, sourced_at
            )
            VALUES (%s, %s, %s, '{}'::jsonb, %s, now(), %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                request_id,
                RequestType.PEOPLE,
                jurisdiction_ocdid,
                requested_by_user_id,
                requested_by_user_id,
            ),
        )


async def register_sheet_import_request(
    request_id: str,
    jurisdiction_ocdid: str,
    requested_by_user_id: str,
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
            INSERT INTO requests (
                id, request_type, jurisdiction_ocdid, requested_by_user_id, batch_id,
                created_at, sourced_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                request_id,
                RequestType.PEOPLE,
                jurisdiction_ocdid,
                requested_by_user_id,
                batch_id,
            ),
        )


async def register_jurisdiction_edit_request(
    request_id: str,
    jurisdiction_ocdid: str,
    arguments_json: dict,
    open_data_url: str,
    requested_by_user_id: Optional[str] = None,
):
    """A hand-edited jurisdiction field. Born published: the edit is already committed."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (
                id, request_type, jurisdiction_ocdid, arguments_json, requested_by_user_id,
                open_data_url, published_at, resolved_by_user_id, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, now(), %s, CURRENT_TIMESTAMP)
            """,
            (
                request_id,
                RequestType.JURISDICTION_MANUAL_EDIT,
                jurisdiction_ocdid,
                json.dumps(arguments_json),
                requested_by_user_id,
                open_data_url,
                requested_by_user_id,
            ),
        )


async def get_request_jurisdiction(request_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid FROM requests WHERE id::text = %s",
            (request_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def jurisdictions_for_requests(request_ids: list[str]) -> dict[str, str]:
    """Which jurisdiction each request is about. The roster itself is derived from that
    request's sightings, so this is all a caller needs to ask for one."""
    if not request_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, jurisdiction_ocdid FROM requests WHERE id::text = ANY(%s)",
            (request_ids,),
        )
        return {request_id: ocdid for request_id, ocdid in await cur.fetchall()}


async def get_request_type(request_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT request_type FROM requests WHERE id::text = %s",
            (request_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def get_issue_request_details(request_ids: list[str]) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.id::text, r.jurisdiction_ocdid, r.arguments_json,
                   COALESCE(j.data->>'name', r.jurisdiction_ocdid) AS jurisdiction_name
            FROM requests r
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.id::text = ANY(%s)
            ORDER BY r.created_at
            """,
            (request_ids,),
        )
        rows = await cur.fetchall()
    return [
        {
            "request_id": r[0],
            "jurisdiction_ocdid": r[1],
            "arguments_json": r[2] or {},
            "jurisdiction_name": r[3],
        }
        for r in rows
    ]


async def dismiss_as_unchanged(cur, request_id: str) -> bool:
    """Retire a scrape that asserted nothing new. Returns whether it was still open.

    Guarded in the statement rather than by checking first: a reviewer may be publishing this
    very request, and losing that race must not overwrite their decision.
    """
    await cur.execute(
        f"""
        UPDATE requests
           SET dismissed_at = now(), dismissed_reason = '{DISMISSED_UNCHANGED}'
         WHERE id::text = %s AND published_at IS NULL AND dismissed_at IS NULL
        """,
        (request_id,),
    )
    return cur.rowcount > 0


async def dismiss_superseded_by(
    cur, request_id: str, jurisdiction_ocdid: str, sourced_at
) -> list[str]:
    """Dismiss the cards this publish just made pointless, in the publishing transaction.

    `_refuse_if_superseded` makes a stale card unpublishable; this stops it being offered at
    all. The sweep still runs — it catches two *pending* scrapes, which have no publish to hang
    off, and re-checks holds as they expire.
    """
    await cur.execute(
        f"""
        UPDATE requests
           SET dismissed_at = now(), dismissed_reason = '{DISMISSED_SUPERSEDED}'
         WHERE id IN (
             SELECT r.id FROM requests r
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
            request_id,
            sourced_at,
            timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),
        ),
    )
    return [row[0] for row in await cur.fetchall()]


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
                FROM requests r
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
                FROM requests r
                WHERE r.published_at IS NOT NULL AND r.sourced_at IS NOT NULL
            )
            UPDATE requests
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
            RETURNING id::text
            """,
            (timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES),),
        )
        return [row[0] for row in await cur.fetchall()]
