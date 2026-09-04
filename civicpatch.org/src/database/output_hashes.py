from database.database import get_pool


async def get_hashes(targets: list[str]) -> dict[str, str]:
    """What we last wrote to each of these destinations. Absent means never written."""
    if not targets:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT target, content_hash FROM output_hashes WHERE target = ANY(%s)",
            (targets,),
        )
        rows = await cur.fetchall()
    return {row[0]: row[1] for row in rows}


async def record_hashes(hashes: dict[str, str]) -> None:
    """Record only what actually landed.

    Called after the write is confirmed — for open-data that is the ref move, not the tree POST.
    Recording earlier would mark a batch written that never reached the branch, and the retry
    would then skip it.
    """
    if not hashes:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO output_hashes (target, content_hash)
            VALUES (%s, %s)
            ON CONFLICT (target)
            DO UPDATE SET content_hash = EXCLUDED.content_hash, written_at = now()
            """,
            list(hashes.items()),
        )
