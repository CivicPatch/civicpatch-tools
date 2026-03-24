import logging
from datetime import date
from enum import StrEnum
from typing import Any
from database.database import get_pool

logger = logging.getLogger(__name__)


class ReviewSessionEntryStatus(StrEnum):
    VIEWING = "viewing"
    SKIPPED = "skipped"
    RESOLVED = "resolved"


async def create_or_get_review_session(
    provider: str,
    provider_user_id: str,
    session_date: date,
    state_code: str,
    daily_goal: int | None = None,
) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if daily_goal is None:
                await cur.execute(
                    """
                    SELECT daily_goal FROM review_sessions
                    WHERE provider = %s AND provider_user_id = %s
                    ORDER BY session_date DESC
                    LIMIT 1
                    """,
                    (provider, provider_user_id),
                )
                row = await cur.fetchone()
                daily_goal = row[0] if row else 10

            await cur.execute(
                """
                INSERT INTO review_sessions
                    (provider, provider_user_id, session_date, state_code, daily_goal)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (provider, provider_user_id, session_date, state_code)
                DO UPDATE SET daily_goal = EXCLUDED.daily_goal
                """,
                (provider, provider_user_id, session_date, state_code, daily_goal),
            )

            await cur.execute(
                """
                SELECT id, state_code, daily_goal, session_date, created_at
                FROM review_sessions
                WHERE provider = %s
                  AND provider_user_id = %s
                  AND session_date = %s
                  AND state_code = %s
                """,
                (provider, provider_user_id, session_date, state_code),
            )
            row = await cur.fetchone()

    return {
        "id": str(row[0]),
        "state_code": row[1],
        "daily_goal": row[2],
        "session_date": row[3].isoformat(),
        "created_at": row[4].isoformat(),
    }


# TODO: rename to get_current_session_with_current_entry 
async def get_today_session_with_current_entry(
    provider: str,
    provider_user_id: str,
    state_code: str,
) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, state_code, daily_goal, session_date, created_at
                FROM review_sessions
                WHERE provider = %s
                  AND provider_user_id = %s
                  AND session_date = CURRENT_DATE
                  AND state_code = %s
                """,
                (provider, provider_user_id, state_code),
            )
            session_row = await cur.fetchone()
            if not session_row:
                return None

            session = {
                "id": str(session_row[0]),
                "state_code": session_row[1],
                "daily_goal": session_row[2],
                "session_date": session_row[3].isoformat(),
                "created_at": session_row[4].isoformat(),
            }

            await cur.execute(
                """
                SELECT
                    rse.id, rse.request_id, rse.jurisdiction_ocdid,
                    rse.status, rse.created_at,
                    j.pull_request_url, j.pull_request_review_state,
                    j.arguments_json->>'jurisdiction_ocdid' AS jurisdiction_ocdid_job,
                    jur.data->>'name' AS jurisdiction_name,
                    j.created_at AS job_created_at,
                    j.updated_at AS job_updated_at
                FROM review_session_entries rse
                JOIN jobs j ON j.request_id = rse.request_id
                LEFT JOIN jurisdictions jur
                    ON jur.jurisdiction_ocdid = rse.jurisdiction_ocdid
                WHERE rse.review_session_id = %s
                  AND rse.status = 'viewing'
                LIMIT 1
                """,
                (session_row[0],),
            )
            entry_row = await cur.fetchone()

            if not entry_row:
                return {"session": session, "current_entry": None}

            entry = {
                "id": str(entry_row[0]),
                "request_id": entry_row[1],
                "jurisdiction_ocdid": entry_row[2],
                "status": entry_row[3],
                "created_at": entry_row[4].isoformat(),
            }
            job = {
                "request_id": entry_row[1],
                "pull_request_url": entry_row[5],
                "pull_request_review_state": entry_row[6],
                "jurisdiction_ocdid": entry_row[7],
                "jurisdiction_name": entry_row[8],
                "created_at": entry_row[9].isoformat() if entry_row[9] else None,
                "updated_at": entry_row[10].isoformat() if entry_row[10] else None,
            }

    return {"session": session, "current_entry": {"entry": entry, "job": job}}


async def advance_review_session(
    review_session_id: str,
) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT state_code, daily_goal FROM review_sessions WHERE id = %s",
                (review_session_id,),
            )
            session_row = await cur.fetchone()
            if not session_row:
                return None
            state_code, daily_goal = session_row[0], session_row[1]

            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'skipped'
                WHERE review_session_id = %s AND status = 'viewing'
                """,
                (review_session_id,),
            )

            await cur.execute(
                "SELECT COUNT(*) FROM review_session_entries WHERE review_session_id = %s",
                (review_session_id,),
            )
            count_row = await cur.fetchone()
            if count_row[0] >= daily_goal:
                return None

            await cur.execute(
                """
                SELECT j.request_id, j.pull_request_url, j.pull_request_review_state,
                       j.arguments_json->>'jurisdiction_ocdid' AS jurisdiction_ocdid,
                       jur.data->>'name' AS jurisdiction_name,
                       j.created_at, j.updated_at
                FROM jobs j
                LEFT JOIN jurisdictions jur
                    ON jur.jurisdiction_ocdid = j.arguments_json->>'jurisdiction_ocdid'
                WHERE j.pull_request_status = 'open'
                  AND j.arguments_json->>'jurisdiction_ocdid' NOT IN (
                      SELECT jurisdiction_ocdid
                      FROM review_session_entries
                      WHERE review_session_id = %s AND status = 'resolved'
                  )
                  AND j.arguments_json->>'jurisdiction_ocdid' NOT IN (
                      SELECT rse.jurisdiction_ocdid
                      FROM review_session_entries rse
                      JOIN review_sessions rs ON rs.id = rse.review_session_id
                      WHERE rse.status = 'viewing'
                        AND rs.session_date = CURRENT_DATE
                        AND rs.id != %s
                  )
                  AND j.arguments_json->>'jurisdiction_ocdid' LIKE %s
                ORDER BY
                    -- skipped items defer to the end; unseen items come first
                    (CASE WHEN j.arguments_json->>'jurisdiction_ocdid' IN (
                        SELECT jurisdiction_ocdid FROM review_session_entries
                        WHERE review_session_id = %s AND status = 'skipped'
                    ) THEN 1 ELSE 0 END) ASC,
                    (j.pull_request_review_state = 'changes_requested') DESC,
                    j.created_at DESC
                LIMIT 1
                """,
                (review_session_id, review_session_id, f"%state:{state_code}%", review_session_id),
            )
            next_row = await cur.fetchone()

            if not next_row:
                return None

            request_id = next_row[0]
            jurisdiction_ocdid = next_row[3]

            await cur.execute(
                """
                INSERT INTO review_session_entries
                    (review_session_id, request_id, jurisdiction_ocdid, status)
                VALUES (%s, %s, %s, 'viewing')
                """,
                (review_session_id, request_id, jurisdiction_ocdid),
            )
            entry_number = count_row[0] + 1

    job = {
        "request_id": request_id,
        "pull_request_url": next_row[1],
        "pull_request_review_state": next_row[2],
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "jurisdiction_name": next_row[4],
        "created_at": next_row[5].isoformat() if next_row[5] else None,
        "updated_at": next_row[6].isoformat() if next_row[6] else None,
    }

    return {"job": job, "entry_number": entry_number}


async def resolve_review_session_entries_by_request_id(request_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved'
                WHERE request_id = %s AND status != 'resolved'
                """,
                (request_id,),
            )


async def resolve_review_session_entries_by_pr_number(pr_number: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved'
                WHERE request_id IN (
                    SELECT request_id FROM jobs
                    WHERE pull_request_url LIKE %s
                )
                AND status != 'resolved'
                """,
                (f"%/pull/{pr_number}",),
            )
