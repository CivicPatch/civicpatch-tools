"""What the scrape steers by, read off cp.org's posts.

These used to test `_roles_from_posts_from_db`, which split `office.name` on " - " and resolved
each part against the taxonomy. A post carries one decided `role_id`, so there is nothing to
split and nothing to resolve — the test for compound office names went with the splitting.
"""

from types import SimpleNamespace

import httpx
import pytest

from runners.people_collector.steps.step_01_research_municipality.research_municipality import (
    _post_memberships,
    _researched_memberships,
    _source_urls,
)
from runners.people_collector.schemas import ExpectedMembership, ResearchedPerson
from shared.schemas import (
    KnownOrganization,
    Membership,
    Post,
    Role,
    RoleConfig,
)
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, build_taxonomy

pytestmark = pytest.mark.unit

_ROLE_CONFIG = RoleConfig(
    roles=[
        Role(id="mayor", label="Mayor"),
        Role(id="council-member", label="Council Member"),
        Role(id="council-president", label="Council President"),
    ]
)

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:buckley/government"
_BASE = "ocd-division/country:us/state:wa/place:buckley"


def _post(role_id: str, division_ocdid: str = _BASE) -> Post:
    return Post(
        id=f"{role_id}:{division_ocdid}",
        jurisdiction_ocdid=_OCDID,
        organization_id="org",
        role_id=role_id,
        division_ocdid=division_ocdid,
        label=role_id,
    )


# --- _post_memberships: one expected membership per known post ---


def test_each_post_is_expected_once_under_its_taxonomy_label_and_division():
    posts = [_post("mayor"), _post("council-member", f"{_BASE}/ward:2")]

    assert _post_memberships(posts, [], _ROLE_CONFIG, _OCDID) == [
        ExpectedMembership(organization_id="org", role_label="Mayor"),
        ExpectedMembership(organization_id="org", role_label="Council Member", division="ward 2"),
    ]


def test_a_post_with_a_headcount_is_still_expected_once():
    """`meta_headcount` is the first scrape's count and never recomputed."""
    at_large = _post("council-member").model_copy(update={"meta_headcount": 5})

    assert len(_post_memberships([at_large], [], _ROLE_CONFIG, _OCDID)) == 1


def test_an_unmatched_post_is_not_expected():
    """`unmatched` is a real post's role and has no label worth searching a page for."""
    expected = _post_memberships([_post(UNMATCHED_ROLE_ID), _post("mayor")], [], _ROLE_CONFIG, _OCDID)

    assert [membership.role_label for membership in expected] == ["Mayor"]


def _held(post: Post, label: str) -> Membership:
    return Membership(
        post_id=post.id,
        role_id=post.role_id,
        division_ocdid=post.division_ocdid,
        role_label="Council Member",
        label=label,
    )


def test_a_post_carries_the_designations_of_every_membership_held_on_it():
    """An at-large post is one expected membership, however many seat markers its holders have."""
    at_large, mayor = _post("council-member"), _post("mayor")
    held = [_held(at_large, "Seat 1"), _held(at_large, "Seat 2"), _held(mayor, "Seat 9")]

    [council] = _post_memberships([at_large], held, _ROLE_CONFIG, _OCDID)

    assert council.designations == ["Seat 1", "Seat 2"]


# --- _researched_memberships: the first scrape, parsed with the shared parser ---

_DEFAULT = KnownOrganization(id="government", name="Government", meta_is_default=True, posts=[])
_OTHER = KnownOrganization(id="schools", name="School Board", posts=[])
_MAYOR_COUNCIL_COUNCIL = KnownOrganization(
    id="council", name="Council", meta_is_default=True, role_labels=["Council Member"]
)
_MAYOR_COUNCIL_MAYOR = KnownOrganization(id="mayor", name="Office of the Mayor", role_labels=["Mayor"])


def _researched(label: str) -> ResearchedPerson:
    return ResearchedPerson(name="Ann Lee", label=label)


def test_research_is_expected_in_the_default_organization():
    """Research knows no organizations. The same `parse_label` cp.org runs at ingest, so a
    first scrape and every later one agree about what a label means."""
    expected = _researched_memberships(
        [_researched("Council Member, Ward 3"), _researched("Mayor")],
        [_OTHER, _DEFAULT],
        build_taxonomy(_ROLE_CONFIG),
    )

    assert expected == [
        ExpectedMembership(organization_id="government", role_label="Council Member", division="ward 3"),
        ExpectedMembership(organization_id="government", role_label="Mayor"),
    ]


def test_each_researched_role_goes_to_the_organization_whose_role_labels_hold_it():
    """Under mayor_council the Mayor is not a Council post, so research must not expect them
    there just because Council is the default."""
    expected = _researched_memberships(
        [_researched("Council Member, Ward 3"), _researched("Mayor")],
        [_MAYOR_COUNCIL_COUNCIL, _MAYOR_COUNCIL_MAYOR],
        build_taxonomy(_ROLE_CONFIG),
    )

    assert [(e.organization_id, e.role_label) for e in expected] == [
        ("council", "Council Member"),
        ("mayor", "Mayor"),
    ]


def test_a_role_no_organization_holds_is_not_expected():
    expected = _researched_memberships(
        [_researched("Council President")],
        [_MAYOR_COUNCIL_MAYOR, _MAYOR_COUNCIL_COUNCIL],
        build_taxonomy(_ROLE_CONFIG),
    )

    assert expected == []


def test_a_researched_label_naming_no_role_is_not_expected():
    """Progress counts by role, so it would count toward nothing."""
    expected = _researched_memberships(
        [_researched("Friend of the Library")], [_DEFAULT], build_taxonomy(_ROLE_CONFIG)
    )

    assert expected == []


def test_a_researched_designation_naming_no_division_is_search_wording_only():
    [council] = _researched_memberships(
        [_researched("Council Member, Position 1")], [_DEFAULT], build_taxonomy(_ROLE_CONFIG)
    )

    assert (council.division, council.designations) == (None, ["Position 1"])


def _config(source_urls: list[str] | None = None):
    return SimpleNamespace(source_urls=source_urls or [])


@pytest.mark.asyncio
async def test_a_configured_list_wins_without_asking_cp_org():
    """A human naming the pages means they know something the last scrape did not."""
    async with httpx.AsyncClient(base_url="http://cp-org.invalid") as client:
        seeds = await _source_urls(_config(["https://zz.gov/only-this"]), client, _OCDID)

    assert seeds == ["https://zz.gov/only-this"]


_SELECT_BOARD_ROLES = RoleConfig(
    roles=[
        Role(id="chair", label="Chair", aliases=["Chairman"], priority=20),
        Role(id="select-board-member", label="Select Board Member", aliases=["Board of Selectmen"], priority=300),
        Role(id="council-member", label="Council Member", aliases=["Member"], priority=500),
        Role(id="clerk", label="Clerk", priority=600),
    ]
)


def test_only_the_organizations_posts_are_expected_whatever_research_calls_them():
    """Research's titles are not ours to choose: a generic Chair or Member the label also names
    loses to the organization's post, and a Town Clerk, which no organization holds, is dropped."""
    select_board = KnownOrganization(
        id="select", name="Select Board", meta_is_default=True, role_labels=["Select Board Member"]
    )

    expected = _researched_memberships(
        [
            _researched("Chairman, Board of Selectmen"),
            _researched("Member, Board of Selectmen"),
            _researched("Town Clerk"),
        ],
        [select_board],
        build_taxonomy(_SELECT_BOARD_ROLES),
    )

    assert [(e.organization_id, e.role_label) for e in expected] == [
        ("select", "Select Board Member"),
        ("select", "Select Board Member"),
    ]
