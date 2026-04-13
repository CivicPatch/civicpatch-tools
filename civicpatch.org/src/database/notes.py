from database.database import get_pool


async def get_notes_for_jurisdiction(jurisdiction_ocdid: str, limit: int, offset: int):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) FROM notes WHERE jurisdiction_ocdid = %s
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
        total = row[0] if row is not None else 0

        await cur.execute(
            """
            SELECT
                n.id::text,
                n.jurisdiction_ocdid,
                n.body,
                n.user_id::text,
                n.created_at,
                CASE WHEN u.provider = 'github'
                    THEN 'https://avatars.githubusercontent.com/u/' || u.provider_user_id
                    ELSE NULL
                END AS avatar_url,
                u.display_name,
                CASE WHEN u.provider = 'github'
                    THEN 'https://github.com/' || u.display_name
                    ELSE NULL
                END AS profile_url
            FROM notes n
            LEFT JOIN users u ON u.id = n.user_id
            WHERE n.jurisdiction_ocdid = %s
            ORDER BY n.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (jurisdiction_ocdid, limit, offset),
        )
        rows = await cur.fetchall()

    notes = [
        {
            "id": r[0],
            "jurisdiction_ocdid": r[1],
            "body": r[2],
            "user_id": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
            "avatar_url": r[5],
            "display_name": r[6],
            "profile_url": r[7],
        }
        for r in rows
    ]
    return total, notes


async def create_note(jurisdiction_ocdid: str, body: str, user_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO notes (jurisdiction_ocdid, body, user_id)
            VALUES (%s, %s, %s)
            RETURNING id::text, jurisdiction_ocdid, body, user_id::text, created_at
            """,
            (jurisdiction_ocdid, body, user_id),
        )
        r = await cur.fetchone()
    if r is None:
        raise RuntimeError("INSERT RETURNING returned no row")
    return {
        "id": r[0],
        "jurisdiction_ocdid": r[1],
        "body": r[2],
        "user_id": r[3],
        "created_at": r[4].isoformat() if r[4] else None,
    }
