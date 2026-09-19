"""Per-organization progress: how many people an organization needs, and whether it has them."""

import pytest
from runners.people_collector.schemas import OrganizationProgress, PersonSourceRecord
from runners.people_collector.steps.step_04_process_page_content.organization_progress import (
    organization_needs,
    organizations_progress,
    is_done,
    required_to_be_done,
)
from shared.schemas import KnownOrganization, Membership, Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

_TAXONOMY = build_taxonomy(
    RoleConfig(roles=[Role(id="mayor", label="Mayor"), Role(id="council-member", label="Council Member")])
)


def _organization(organization_id: str) -> KnownOrganization:
    return KnownOrganization(id=organization_id, name=organization_id, posts=[])


def _member(organization_id: str, role_label: str, post_label: str = "") -> Membership:
    return Membership(
        post_id=f"{organization_id}-{post_label or role_label}",
        organization_id=organization_id,
        role_id=role_label.lower().replace(" ", "-"),
        division_ocdid="ocd-division/country:us/state:wa/place:seattle",
        role_label=role_label,
        post_label=post_label or role_label,
    )


def _council(count: int) -> list[Membership]:
    return [_member("council", "Council Member", f"Council Member District {n}") for n in range(1, count + 1)]


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
    assert organizations_progress([_organization("council")], _council(9), {}, _TAXONOMY) == []


def test_each_organization_counts_only_people_stamped_with_it():
    records = {
        "Rob Saka": _person("Rob Saka", "Council Member District 1", "council"),
        "Eddie Lin": _person("Eddie Lin", "Council Member District 2", "council"),
        "Katie Wilson": _person("Katie Wilson", "Mayor", "mayor"),
    }

    progress = organizations_progress(
        [_organization("council"), _organization("mayor")],
        _council(3) + [_member("mayor", "Mayor")],
        records,
        _TAXONOMY,
    )

    assert progress == [
        OrganizationProgress(organization_id="council", required=3, found=2),
        OrganizationProgress(organization_id="mayor", required=1, found=1),
    ]


def test_known_memberships_are_what_an_organization_requires():
    """Not `meta_headcount`, which is the first scrape's count and never recomputed: a vacant
    post has nobody to find, and a five-member at-large post has five."""
    [council, _] = organizations_progress(
        [_organization("council"), _organization("mayor")],
        [_member("council", "Council Member", "Council Member At Large")] * 5,
        {},
        _TAXONOMY,
    )

    assert council.required == 5


def test_a_person_without_role_or_contact_details_is_not_counted():
    records = {"Rob Saka": _person("Rob Saka", "Council Member District 1", "council", phone=None)}

    [council, _] = organizations_progress(
        [_organization("council"), _organization("mayor")],
        _council(1) + [_member("mayor", "Mayor")],
        records,
        _TAXONOMY,
    )

    assert council.found == 0


def test_a_single_organization_still_steers_by_its_missing_members():
    """Greensboro's mayor sits on the council: one organization, and the member nobody found yet
    is what should pull their page forward."""
    records = {
        "Crystal Black": _person("Crystal Black", "Council Member District 1", "council"),
        "Cecile Crawford": _person("Cecile Crawford", "Council Member District 2", "council"),
    }

    [need] = organization_needs(
        [_organization("council")],
        [_member("council", "Mayor")] + _council(2),
        records,
        _TAXONOMY,
    )

    assert need.shortfall == pytest.approx(1 / 3)
    assert need.missing_terms == ["mayor"]


def test_the_organization_furthest_from_done_needs_most():
    records = {"Rob Saka": _person("Rob Saka", "Council Member District 1", "council")}

    council, mayor = organization_needs(
        [_organization("council"), _organization("mayor")],
        _council(1) + [_member("mayor", "Mayor")],
        records,
        _TAXONOMY,
    )

    assert (council.shortfall, mayor.shortfall) == (0.0, 1.0)
    assert (council.missing_terms, mayor.missing_terms) == ([], ["mayor"])


def test_missing_members_are_counted_per_role():
    """Two of three council members found: as tokens every council label is the same words, so
    the role is what is missing, not District 3."""
    records = {
        "Rob Saka": _person("Rob Saka", "Council Member District 1", "council"),
        "Eddie Lin": _person("Eddie Lin", "Council Member District 2", "council"),
    }

    [need] = organization_needs([_organization("council")], _council(3), records, _TAXONOMY)

    assert need.missing_terms == ["council", "member", "district"]
