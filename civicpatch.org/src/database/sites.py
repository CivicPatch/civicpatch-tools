"""The websites jurisdictions and their organizations are known by."""

from core.source_sites import SiteOwner
from database.database import get_pool


async def site_owners() -> list[SiteOwner]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, NULL, data->>'url'
              FROM jurisdictions
             WHERE COALESCE(data->>'url', '') <> ''
            UNION ALL
            SELECT jurisdiction_ocdid, id::text, url
              FROM organizations
             WHERE COALESCE(url, '') <> ''
            """
        )
        rows = await cur.fetchall()
    return [
        SiteOwner(jurisdiction_ocdid=ocdid, organization_id=organization_id, url=url)
        for ocdid, organization_id, url in rows
    ]
