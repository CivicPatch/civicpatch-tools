import json

from core.activity import summarize_activity
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.activity import Change, ChangedJurisdiction
from shared.utils.statuses import ActivityType, DismissalReason


async def get_activity_for_roles(
    roles: list[str] | None, limit: int, offset: int
) -> tuple[int, list[dict]]:
    """`roles=None` is no filter at all — every author. A list narrows to just those roles."""
    role_filter = "AND u.role = ANY(%s)" if roles is not None else ""
    params = (roles,) if roles is not None else ()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT COUNT(*)
            FROM activity a
            JOIN users u ON u.id = a.user_id
            WHERE true {role_filter}
            """,
            params,
        )
        count_row = await cur.fetchone()
        total = count_row[0] if count_row is not None else 0

        await cur.execute(
            f"""
            SELECT a.id::text, a.type, a.jurisdiction_ocdid, a.changeset_id,
                   a.changes, a.created_at,
                   u.username AS author_name, u.role AS author_role,
                   COALESCE(j.data->>'name', a.jurisdiction_ocdid) AS jurisdiction_name,
                   changesets.change_url AS pull_request_url
            FROM activity a
            JOIN users u ON u.id = a.user_id
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = a.jurisdiction_ocdid
            LEFT JOIN changesets ON changesets.id::text = a.changeset_id
            WHERE true {role_filter}
            ORDER BY a.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
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
            "summary": summarize_activity(r[1], r[4]),
        }
        for r in rows
    ]


async def get_recent_publications(limit: int) -> list[dict]:
    """Public proof-of-life feed: publish events only, no author diff or review detail.

    Grouped by jurisdiction + day — several publishes on the same town in one day collapse to
    a single row (the latest one), with `review_count` saying how many. Without this, one
    actively-touched town could fill the whole feed and crowd out everything else.

    `kind` names the changeset that went live (`scrape`, `people_edit`, `sheet_import`,
    `rollback`) — every publish writes the *same* `publish_review` activity type regardless of
    what actually produced it (a scrape a reviewer approved, a maintainer's hand edit, a
    rollback), so `kind` is the only column that tells them apart for display.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            WITH publish_events AS (
                SELECT a.jurisdiction_ocdid,
                       a.created_at,
                       a.user_id,
                       changesets.change_url AS commit_url,
                       changesets.kind,
                       COUNT(*) OVER (
                           PARTITION BY a.jurisdiction_ocdid, date_trunc('day', a.created_at)
                       ) AS review_count
                FROM activity a
                LEFT JOIN changesets ON changesets.id::text = a.changeset_id
                WHERE a.type = 'publish_review'
            ),
            latest_per_group AS (
                SELECT DISTINCT ON (jurisdiction_ocdid, date_trunc('day', created_at))
                       jurisdiction_ocdid, created_at, user_id, commit_url, kind, review_count
                FROM publish_events
                ORDER BY jurisdiction_ocdid, date_trunc('day', created_at), created_at DESC
            )
            SELECT g.jurisdiction_ocdid,
                   COALESCE(j.data->>'name', g.jurisdiction_ocdid) AS jurisdiction_name,
                   j.state,
                   u.username AS author_name,
                   u.role AS author_role,
                   g.commit_url,
                   g.kind,
                   g.created_at,
                   g.review_count
            FROM latest_per_group g
            JOIN users u ON u.id = g.user_id
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = g.jurisdiction_ocdid
            ORDER BY g.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = await cur.fetchall()
    return [
        {
            "jurisdiction_ocdid": r[0],
            "jurisdiction_name": r[1],
            "state": r[2],
            "author_name": r[3],
            "author_role": r[4],
            "commit_url": r[5],
            "kind": r[6],
            "created_at": r[7],
            "review_count": r[8],
        }
        for r in rows
    ]


async def create_activity_row(
    change_type: ActivityType,
    user_id: str | None,
    jurisdiction_ocdid: str | None = None,
    changeset_id: str | None = None,
    changes: Change | None = None,
) -> None:
    payload = json.dumps(changes.model_dump()) if changes else None
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO activity (type, jurisdiction_ocdid, changeset_id, changes, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (change_type, jurisdiction_ocdid, changeset_id, payload, user_id or SYSTEM_USER_ID),
        )


async def create_activity_rows(
    entries: list[tuple[ActivityType, Change | None]],
    user_id: str | None,
    jurisdiction_ocdid: str | None = None,
    changeset_id: str | None = None,
) -> None:
    """A whole save's worth of activity rows, on one connection.

    `create_activity_row` above takes a connection *per row* — a reviewer's edit to five people
    checked five out of a pool of twenty, one after another, which costs more than the insert
    it wraps. One `executemany` here instead.

    Still its own connection rather than a caller's cursor: these are recorded best-effort
    beside a publish that already committed, which is `record_change`'s job and not this one's.
    """
    if not entries:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO activity (type, jurisdiction_ocdid, changeset_id, changes, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (
                    change_type,
                    jurisdiction_ocdid,
                    changeset_id,
                    json.dumps(changes.model_dump()) if changes else None,
                    user_id or SYSTEM_USER_ID,
                )
                for change_type, changes in entries
            ],
        )


async def record_change(
    cur,
    change_type: ActivityType,
    user_id: str | None,
    jurisdiction_ocdid: str | None = None,
    changes: Change | None = None,
    changeset_id: str | None = None,
) -> None:
    """Write an activity row on an existing cursor, so it commits with what it describes.

    `create_activity_row` above opens its own connection and cannot do that. Callers already
    inside a transaction use this one.

    `changeset_id` names the scrape responsible, for the events no person asked for — a post
    minted because a source listed a seat. With no user and no request a row says only that
    something happened, which is not enough to act on.
    """
    await cur.execute(
        """
        INSERT INTO activity (type, jurisdiction_ocdid, changes, user_id, changeset_id)
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

    No payload: `reason` is a parameter here only so callers keep passing it to the column.
    `changesets.dismissed_reason` is where it lands and where every reader asks — the log used
    to carry a second copy for nobody.
    """
    await record_change(
        cur,
        ActivityType.DISMISS_REVIEW,
        user_id,
        jurisdiction_ocdid,
        changeset_id=changeset_id,
    )


async def jurisdictions_changed_since(minutes: int) -> list[ChangedJurisdiction]:
    """Which jurisdictions have changed in the last `minutes`, and how.

    `states_changed_since` for the sink whose unit is a file rather than a tab: open-data holds
    one file per jurisdiction, so it needs the ocdid and not the state.

    Global rows carry no jurisdiction and name no file, so they are excluded here for the same
    reason they are there. `dismiss_review` too: a dismissal ends a review without touching a row,
    and 245 of the 294 so far were superseded — a newer scrape won, so the roster is unchanged.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid,
                   array_agg(DISTINCT type) AS types,
                   array_remove(array_agg(DISTINCT changeset_id), NULL) AS changeset_ids
            FROM activity
            WHERE created_at > now() - make_interval(mins => %s)
              AND jurisdiction_ocdid IS NOT NULL
              AND type <> %s
            GROUP BY jurisdiction_ocdid
            ORDER BY jurisdiction_ocdid
            """,
            (minutes, ActivityType.DISMISS_REVIEW),
        )
        rows = await cur.fetchall()
    return [
        ChangedJurisdiction(
            jurisdiction_ocdid=ocdid,
            change_types=sorted(types),
            changeset_ids=sorted(changeset_ids),
        )
        for ocdid, types, changeset_ids in rows
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

    `dismiss_review` is skipped for a different reason — a dismissal moves no row at all.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT substring(jurisdiction_ocdid from 'state:([a-z]{2})') AS state
            FROM activity
            WHERE created_at > now() - make_interval(mins => %s)
              AND jurisdiction_ocdid IS NOT NULL
              AND type <> %s
            """,
            (minutes, ActivityType.DISMISS_REVIEW),
        )
        rows = await cur.fetchall()
    return sorted(row[0] for row in rows if row[0])
