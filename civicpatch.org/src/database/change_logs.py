import json

from database.change_log_summary import summarize_change_log
from database.database import get_pool
from database.requests import REVIEW_STATUS
from schemas.change_logs import (
    AssertionChangePayload,
    JurisdictionChangePayload,
    MembershipChangePayload,
    PersonChangePayload,
    PostChangePayload,
)
from shared.utils.statuses import ChangeLogType


async def get_change_logs_for_roles(roles: list[str], limit: int, offset: int) -> tuple[int, list[dict]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*)
            FROM change_logs cl
            JOIN users u ON u.id = cl.user_id
            WHERE u.role = ANY(%s)
            """,
            (roles,),
        )
        count_row = await cur.fetchone()
        total = count_row[0] if count_row is not None else 0

        await cur.execute(
            """
            SELECT cl.id::text, cl.type, cl.jurisdiction_ocdid, cl.request_id,
                   cl.changes, cl.created_at,
                   COALESCE(u.display_name, 'Anonymous') AS author_name, u.role AS author_role,
                   COALESCE(j.data->>'name', cl.jurisdiction_ocdid) AS jurisdiction_name,
                   r.open_data_url AS pull_request_url
            FROM change_logs cl
            JOIN users u ON u.id = cl.user_id
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = cl.jurisdiction_ocdid
            LEFT JOIN requests r ON r.id::text = cl.request_id
            WHERE u.role = ANY(%s)
            ORDER BY cl.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (roles, limit, offset),
        )
        rows = await cur.fetchall()
    return total, [
        {
            "id": r[0],
            "type": r[1],
            "jurisdiction_ocdid": r[2],
            "request_id": r[3],
            "changes": r[4],
            "created_at": r[5],
            "author_name": r[6],
            "author_role": r[7],
            "jurisdiction_name": r[8],
            "pull_request_url": r[9],
            "summary": summarize_change_log(r[1], r[4]),
        }
        for r in rows
    ]


async def create_change_log(
    change_type: ChangeLogType,
    user_id: str | None,
    jurisdiction_ocdid: str | None = None,
    request_id: str | None = None,
    changes: PersonChangePayload | JurisdictionChangePayload | None = None,
) -> None:
    payload = json.dumps(changes.model_dump()) if changes else None
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO change_logs (type, jurisdiction_ocdid, request_id, changes, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (change_type, jurisdiction_ocdid, request_id, payload, user_id),
        )


async def record_change(
    cur,
    change_type: ChangeLogType,
    user_id: str | None,
    jurisdiction_ocdid: str | None = None,
    changes: PostChangePayload | MembershipChangePayload | AssertionChangePayload | None = None,
) -> None:
    """Write a change log on an existing cursor, so it commits with what it describes.

    `create_change_log` above opens its own connection and cannot do that. Callers already
    inside a transaction use this one.
    """
    await cur.execute(
        """
        INSERT INTO change_logs (type, jurisdiction_ocdid, changes, user_id)
        VALUES (%s, %s, %s, %s)
        """,
        (
            change_type,
            jurisdiction_ocdid,
            json.dumps(changes.model_dump()) if changes else None,
            user_id,
        ),
    )
