from database.database import get_pool


async def get_synced_file_shas() -> dict[str, str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT path, blob_sha FROM synced_files")
        rows = await cur.fetchall()
    return {row[0]: row[1] for row in rows}


async def upsert_synced_file(path: str, blob_sha: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO synced_files (path, blob_sha)
            VALUES (%s, %s)
            ON CONFLICT (path)
            DO UPDATE SET blob_sha = EXCLUDED.blob_sha, synced_at = now()
            """,
            (path, blob_sha),
        )


async def delete_synced_files(paths: list[str]) -> None:
    if not paths:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM synced_files WHERE path = ANY(%s)",
            (paths,),
        )
