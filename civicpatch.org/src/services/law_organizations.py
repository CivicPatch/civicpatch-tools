"""A place's organizations follow its law once pipeline 2 has answered: the ones its posts name are
created, and the ones it does not name go once empty: no source records here, and `organizations_db.delete`
keeps the default and any that still holds posts. Nobody is moved by guesswork; a rescrape empties the rest."""

import database.organizations as organizations_db
from core.organization_build import FormOrganizationRow, law_organization_names, organizations_not_in_law
from database.database import get_pool
from shared.schemas import GoverningLawOrganizations


async def apply_law_organizations(jurisdiction_ocdid: str, answer: GoverningLawOrganizations) -> None:
    names = law_organization_names(answer)
    if names is None:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await organizations_db.ensure_form_organizations(
            cur, [FormOrganizationRow(jurisdiction_ocdid=jurisdiction_ocdid, name=name) for name in names]
        )
        existing = {row["id"]: row["name"] for row in await organizations_db.list_for_jurisdiction(cur, jurisdiction_ocdid)}
        not_in_law = organizations_not_in_law(existing, names)
        holding_people = await organizations_db.ids_with_source_records(cur, not_in_law)
        await conn.commit()
    for organization_id in not_in_law:
        if organization_id not in holding_people:
            await organizations_db.delete(organization_id)
