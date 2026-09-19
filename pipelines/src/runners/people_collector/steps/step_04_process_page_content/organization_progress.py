"""How far each organization's roster is along, when a jurisdiction has several. Pure."""

from collections import Counter
from typing import List

from runners.people_collector.schemas import (
    OrganizationNeed,
    OrganizationProgress,
    PeopleByName,
    PersonSourceRecord,
)
from runners.people_collector.utils.link_discovery import has_role_and_contact_info
from runners.people_collector.utils.organization_terms import as_tokens, organization_phrases
from shared.schemas import KnownOrganization, Membership
from shared.utils.label_parser import parse_label
from shared.utils.taxonomy import Taxonomy


def required_to_be_done(required: int) -> int:
    """Every known member of a small organization, about 80% of a large one — someone we hold can
    have left since, and no page will list them. A one-member Office of the Mayor needs its one."""
    return max(1, required - required // 5)


def is_done(organization: OrganizationProgress) -> bool:
    return organization.found >= required_to_be_done(organization.required)


def organizations_progress(
    organizations: List[KnownOrganization],
    memberships: List[Membership],
    records: PeopleByName,
    taxonomy: Taxonomy,
) -> List[OrganizationProgress]:
    """Nothing for a single organization: its progress stays the jurisdiction-wide count."""
    if len(organizations) < 2:
        return []
    complete = _complete(records, taxonomy)
    return [
        OrganizationProgress(
            organization_id=organization.id,
            required=len(_held_in(organization, memberships)),
            found=len(_found_in(organization, complete)),
        )
        for organization in organizations
    ]


def organization_needs(
    organizations: List[KnownOrganization],
    memberships: List[Membership],
    records: PeopleByName,
    taxonomy: Taxonomy,
) -> List[OrganizationNeed]:
    """Every organization, a single one included: its missing posts still steer the crawl."""
    complete = _complete(records, taxonomy)
    return [
        _organization_need(organization, memberships, _found_in(organization, complete), taxonomy)
        for organization in organizations
    ]


def _complete(records: PeopleByName, taxonomy: Taxonomy) -> List[List[PersonSourceRecord]]:
    return [group for group in records.values() if has_role_and_contact_info(taxonomy, group)]


def _held_in(organization: KnownOrganization, memberships: List[Membership]) -> List[Membership]:
    return [membership for membership in memberships if membership.organization_id == organization.id]


def _found_in(
    organization: KnownOrganization, groups: List[List[PersonSourceRecord]]
) -> List[List[PersonSourceRecord]]:
    return [
        group
        for group in groups
        if any(record.organization_id == organization.id for record in group)
    ]


def _organization_need(
    organization: KnownOrganization,
    memberships: List[Membership],
    found: List[List[PersonSourceRecord]],
    taxonomy: Taxonomy,
) -> OrganizationNeed:
    held = _held_in(organization, memberships)
    target = required_to_be_done(len(held))
    return OrganizationNeed(
        organization_id=organization.id,
        shortfall=max(0, target - len(found)) / target,
        terms=as_tokens(organization_phrases([organization], memberships)),
        missing_terms=as_tokens(_missing_phrases(held, found, taxonomy)),
    )


def _missing_phrases(
    held: List[Membership], found: List[List[PersonSourceRecord]], taxonomy: Taxonomy
) -> List[str]:
    """How the memberships of a role are worded, when fewer people were found in it than hold it.
    Per role, not per post: as tokens, "District 3" and "District 7" are the same words."""
    found_by_role: Counter[str] = Counter(
        role
        for group in found
        for role in {parse_label(record.label, taxonomy).role for record in group if record.label}
        if role
    )
    held_by_role = Counter(membership.role_label for membership in held)
    return [
        phrase
        for membership in held
        if found_by_role[membership.role_label] < held_by_role[membership.role_label]
        for phrase in [membership.post_label, membership.label or "", *membership.source_labels]
    ]
