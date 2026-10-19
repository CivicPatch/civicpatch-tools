"""Queries for `governing_law_source_pages`: the governing_law_collector's own pages, apart
from the people scrape's `source_pages`. Write-once."""

from datetime import datetime, timedelta

from database.database import get_pool
from shared.schemas import GoverningLawSourcePage

_COLUMNS = "id::text, jurisdiction_ocdid, source_url, page_hash, cache_path, collected_at"


def _page(row: tuple) -> GoverningLawSourcePage:
    return GoverningLawSourcePage(
        id=row[0], jurisdiction_ocdid=row[1], source_url=row[2], page_hash=row[3], cache_path=row[4], collected_at=row[5]
    )


async def insert_governing_law_source_page(
    jurisdiction_ocdid: str, source_url: str, page_hash: str, cache_path: str, collected_at: datetime | None
) -> GoverningLawSourcePage:
    """`collected_at` None is now; a reused page keeps the time its text was actually fetched."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            INSERT INTO governing_law_source_pages (jurisdiction_ocdid, source_url, page_hash, cache_path, collected_at)
            VALUES (%s, %s, %s, %s, coalesce(%s, now()))
            RETURNING {_COLUMNS}
            """,
            (jurisdiction_ocdid, source_url, page_hash, cache_path, collected_at),
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row, "RETURNING always yields the inserted row"
    return _page(row)


async def get_governing_law_source_page(jurisdiction_ocdid: str, source_page_id: str) -> GoverningLawSourcePage | None:
    """None for an id that is not one of this jurisdiction's pages."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {_COLUMNS} FROM governing_law_source_pages WHERE jurisdiction_ocdid = %s AND id::text = %s",
            (jurisdiction_ocdid, source_page_id),
        )
        row = await cur.fetchone()
    return _page(row) if row else None


async def get_recent_governing_law_source_page(source_url: str, within: timedelta) -> GoverningLawSourcePage | None:
    """The newest page any jurisdiction collected from this url within the window."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT {_COLUMNS} FROM governing_law_source_pages
            WHERE source_url = %s AND collected_at >= now() - %s
            ORDER BY collected_at DESC LIMIT 1
            """,
            (source_url, within),
        )
        row = await cur.fetchone()
    return _page(row) if row else None
