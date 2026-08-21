"""Database queries for `divisions` — the registry of places a post can point at.

A row is the ocdid and nothing else: type, value and display name are all derivable from it,
and the frontend already renders "Ward 3" that way. What earns the table is authorship — we
publish hyperlocal division ids, so they need a canonical row — plus a FK stopping a post
pointing at a division nobody registered.

Populated lazily, on first use, for the same reason organizations are.
"""


async def find_or_create(cur, ocdid: str, jurisdiction_ocdid: str) -> str:
    """Register a division if it is new. Returns the ocdid, which is the key.

    Nothing is read back: the caller already knows the ocdid, and there is no other column to
    learn. `DO NOTHING` makes a second scrape of the same ward a no-op rather than a conflict.
    """
    await cur.execute(
        """
        INSERT INTO divisions (ocdid, jurisdiction_ocdid)
        VALUES (%s, %s)
        ON CONFLICT (ocdid) DO NOTHING
        """,
        (ocdid, jurisdiction_ocdid),
    )
    return ocdid


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[str]:
    await cur.execute(
        "SELECT ocdid FROM divisions WHERE jurisdiction_ocdid = %s ORDER BY ocdid",
        (jurisdiction_ocdid,),
    )
    return [row[0] for row in await cur.fetchall()]
