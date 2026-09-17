"""Per-organization progress: how many people an organization needs, and whether it has them."""

import pytest
from runners.people_collector.schemas import OrganizationProgress, PersonSourceRecord
from runners.people_collector.steps.step_04_process_page_content.organization_progress import (
    organizations_progress,
    is_done,
    required_to_be_done,
)
from shared.schemas import KnownOrganization, Post, Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_TAXONOMY = build_taxonomy(
    RoleConfig(roles=[Role(id="mayor", label="Mayor"), Role(id="council-member", label="Council Member")])
)


def _organization(organization_id: str, headcounts: list[int]) -> KnownOrganization:
    return KnownOrganization(
        id=organization_id,
        name=organization_id,
        posts=[
            Post(
                id=f"{organization_id}-{i}",
                jurisdiction_ocdid=_OCDID,
                organization_id=organization_id,
                role_id="role",
                division_ocdid="ocd-division/country:us/state:wa/place:seattle",
                label="post",
                meta_headcount=headcount,
            )
            for i, headcount in enumerate(headcounts)
        ],
    )


def _person(name: str, label: str, organization_id: str | None, phone: str | None = "206-684-2489"):
    return [
        PersonSourceRecord(
            name=name, label=label, source_url="https://seattle.gov", phone=phone, organization_id=organization_id
        )
    ]


@pytest.mark.parametrize(
    ("required", "needed"),
    [(0, 1), (1, 1), (2, 2), (3, 3), (4, 4), (5, 4), (10, 8)],
)
def test_small_organizations_must_be_complete_and_large_ones_mostly(required, needed):
    assert required_to_be_done(required) == needed


def test_an_organization_is_done_at_its_own_count():
    assert is_done(OrganizationProgress(organization_id="mayor", required=1, found=1))
    assert not is_done(OrganizationProgress(organization_id="mayor", required=1, found=0))


def test_a_single_organization_has_no_per_organization_progress():
    assert organizations_progress([_organization("council", [1] * 9)], {}, _TAXONOMY) == []


def test_each_organization_counts_only_people_stamped_with_it():
    records = {
        "Rob Saka": _person("Rob Saka", "Council Member District 1", "council"),
        "Eddie Lin": _person("Eddie Lin", "Council Member District 2", "council"),
        "Katie Wilson": _person("Katie Wilson", "Mayor", "mayor"),
    }

    progress = organizations_progress([_organization("council", [1, 1, 1]), _organization("mayor", [1])], records, _TAXONOMY)

    assert progress == [
        OrganizationProgress(organization_id="council", required=3, found=2),
        OrganizationProgress(organization_id="mayor", required=1, found=1),
    ]


def test_headcount_is_what_an_organization_requires():
    """A five-member at-large post is one post and five people to find."""
    [council, _] = organizations_progress([_organization("council", [5]), _organization("mayor", [1])], {}, _TAXONOMY)

    assert council.required == 5


def test_a_person_without_role_or_contact_details_is_not_counted():
    records = {"Rob Saka": _person("Rob Saka", "Council Member District 1", "council", phone=None)}

    [council, _] = organizations_progress([_organization("council", [1]), _organization("mayor", [1])], records, _TAXONOMY)

    assert council.found == 0
