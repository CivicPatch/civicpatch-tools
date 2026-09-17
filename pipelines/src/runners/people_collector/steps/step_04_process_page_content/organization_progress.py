"""How far each organization's roster is along, when a jurisdiction has several. Pure."""

from typing import List

from runners.people_collector.schemas import OrganizationProgress, PeopleByName
from runners.people_collector.utils.link_discovery import has_role_and_contact_info
from shared.schemas import KnownOrganization
from shared.utils.taxonomy import Taxonomy


def required_to_be_done(required: int) -> int:
    """Every post of a small organization, about 80% of a large one — a roster we already hold can
    name a post since vacated, which no page will ever fill. A one-post Office of the Mayor needs its one."""
    return max(1, required - required // 5)


def is_done(organization: OrganizationProgress) -> bool:
    return organization.found >= required_to_be_done(organization.required)


def organizations_progress(
    organizations: List[KnownOrganization], records: PeopleByName, taxonomy: Taxonomy
) -> List[OrganizationProgress]:
    """Nothing for a single organization: its progress stays the jurisdiction-wide count."""
    if len(organizations) < 2:
        return []
    complete = [group for group in records.values() if has_role_and_contact_info(taxonomy, group)]
    return [
        OrganizationProgress(
            organization_id=organization.id,
            required=sum(post.meta_headcount for post in organization.posts),
            found=sum(
                1
                for group in complete
                if any(record.organization_id == organization.id for record in group)
            ),
        )
        for organization in organizations
    ]
