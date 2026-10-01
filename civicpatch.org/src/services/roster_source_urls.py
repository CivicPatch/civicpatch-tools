import database.organizations as organizations_db
import database.people as people_db
from database.database import get_pool
from schemas.jurisdictions import OrganizationRosterSourceUrls
from core.roster_source_urls import roster_source_urls_by_organization


async def get_roster_source_urls(jurisdiction_ocdid: str) -> list[OrganizationRosterSourceUrls]:
    people = await people_db.get_person_models(jurisdiction_ocdid)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organizations = await organizations_db.list_for_jurisdiction(cur, jurisdiction_ocdid)
    names = {organization["id"]: organization["name"] for organization in organizations}
    return [
        OrganizationRosterSourceUrls(
            organization_id=group.organization_id,
            organization_name=names[group.organization_id],
            urls=group.urls,
        )
        for group in roster_source_urls_by_organization(people, list(names))
    ]
