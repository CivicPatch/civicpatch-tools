import json

from core.change_logs import summarize_change_log
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.change_logs import (
    ChangedJurisdiction,
    DismissalPayload,
    AssertionChangePayload,
    JurisdictionChangePayload,
    MembershipChangePayload,
    PersonChangePayload,
    PostChangePayload,
)
from shared.utils.statuses import ChangeLogType, DismissalReason


async def get_change_logs_for_roles(
    roles: list[str], limit: int, offset: int
) -> tuple[int, list[dict]]:
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
            SELECT cl.id::text, cl.type, cl.jurisdiction_ocdid, cl.changeset_id,
                   cl.changes, cl.created_at,
                   COALESCE(u.display_name, 'Anonymous') AS author_name, u.role AS author_role,
                   COALESCE(j.data->>'name', cl.jurisdiction_ocdid) AS jurisdiction_name,
                   r.change_url AS pull_request_url
            FROM change_logs cl
            JOIN users u ON u.id = cl.user_id
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = cl.jurisdiction_ocdid
            LEFT JOIN changesets r ON r.id::text = cl.changeset_id
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
            "changeset_id": r[3],
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
    changeset_id: str | None = None,
    changes: PersonChangePayload | JurisdictionChangePayload | None = None,
) -> None:
    payload = json.dumps(changes.model_dump()) if changes else None
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO change_logs (type, jurisdiction_ocdid, changeset_id, changes, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (change_type, jurisdiction_ocdid, changeset_id, payload, user_id or SYSTEM_USER_ID),
        )


async def record_change(
    cur,
    change_type: ChangeLogType,
    user_id: str | None,
    jurisdiction_ocdid: str | None = None,
    changes: PersonChangePayload
    | PostChangePayload
    | MembershipChangePayload
    | AssertionChangePayload
    | JurisdictionChangePayload
    | DismissalPayload
    | None = None,
    changeset_id: str | None = None,
) -> None:
    """Write a change log on an existing cursor, so it commits with what it describes.

    `create_change_log` above opens its own connection and cannot do that. Callers already
    inside a transaction use this one.

    `changeset_id` names the scrape responsible, for the events no person asked for — a post
    minted because a source listed a seat. With no user and no request a row says only that
    something happened, which is not enough to act on.
    """
    await cur.execute(
        """
        INSERT INTO change_logs (type, jurisdiction_ocdid, changes, user_id, changeset_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            change_type,
            jurisdiction_ocdid,
            json.dumps(changes.model_dump()) if changes else None,
            user_id or SYSTEM_USER_ID,
            changeset_id,
        ),
    )


async def record_dismissal(
    cur,
    changeset_id: str,
    jurisdiction_ocdid: str | None,
    user_id: str | None,
    reason: DismissalReason,
) -> None:
    """The history entry for a changeset leaving the review pool.

    Every dismissal writes one, including the four nobody asked for. `changesets` is current
    state and gets overwritten; this is the record of what happened, and it stores the reason
    rather than leaving it to be derived — `status` and `resolved_by_user_id` are both mutable,
    so a derivation could give a past event a meaning it never had.

    `user_id` is NULL for the machine reasons, which is the honest answer: nobody decided.
    """
    await record_change(
        cur,
        ChangeLogType.CLOSE_REVIEW,
        user_id,
        jurisdiction_ocdid,
        DismissalPayload(reason=reason),
        changeset_id=changeset_id,
    )


async def jurisdictions_changed_since(minutes: int) -> list[ChangedJurisdiction]:
    """Which jurisdictions have changed in the last `minutes`, and how.

    `states_changed_since` for the sink whose unit is a file rather than a tab: open-data holds
    one file per jurisdiction, so it needs the ocdid and not the state.

    Global rows carry no jurisdiction and name no file, so they are excluded here for the same
    reason they are there. `close_review` too: a dismissal ends a review without touching a row,
    and 245 of the 294 so far were superseded — a newer scrape won, so the roster is unchanged.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, array_agg(DISTINCT type) AS types
            FROM change_logs
            WHERE created_at > now() - make_interval(mins => %s)
              AND jurisdiction_ocdid IS NOT NULL
              AND type <> %s
            GROUP BY jurisdiction_ocdid
            ORDER BY jurisdiction_ocdid
            """,
            (minutes, ChangeLogType.CLOSE_REVIEW),
        )
        rows = await cur.fetchall()
    return [
        ChangedJurisdiction(jurisdiction_ocdid=ocdid, change_types=sorted(types))
        for ocdid, types in rows
    ]


async def states_changed_since(minutes: int) -> list[str]:
    """Which states have had a jurisdiction-scoped change in the last `minutes`.

    The feed the outward mirrors run on. Complete because `record_change` writes on the cursor
    it mutates with — watching the tables instead would miss deletes, which is what a mirror
    most needs to see.

    A lookback window rather than a stored cursor, so no migration.

    Rows with no jurisdiction are the global ones — role edits, which rename something every
    state derives a label from. Deliberately not chased: the next change in a state carries the
    new wording anyway, so a rename reaches the sheet as those states are next touched.

    `close_review` is skipped for a different reason — a dismissal moves no row at all.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT substring(jurisdiction_ocdid from 'state:([a-z]{2})') AS state
            FROM change_logs
            WHERE created_at > now() - make_interval(mins => %s)
              AND jurisdiction_ocdid IS NOT NULL
              AND type <> %s
            """,
            (minutes, ChangeLogType.CLOSE_REVIEW),
        )
        rows = await cur.fetchall()
    return sorted(row[0] for row in rows if row[0])
