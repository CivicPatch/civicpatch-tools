"""What the scrape steers by, read off cp.org's posts.

These used to test `_roles_from_posts_from_db`, which split `office.name` on " - " and resolved
each part against the taxonomy. A post carries one decided `role_id`, so there is nothing to
split and nothing to resolve — the test for compound office names went with the splitting.
"""

from types import SimpleNamespace

import pytest

from runners.people_collector.steps.step_01_research_municipality.research_municipality import (
    _post_memberships,
    _researched_memberships,
    _source_urls,
)
from runners.people_collector.schemas import ExpectedMembership, ResearchedPerson
from shared.schemas import KnownOrganization, Membership, Person, Post, Role, RoleConfig
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


def _held(post: Post, designations: list[str]) -> Membership:
    return Membership(
        post_id=post.id,
        role_id=post.role_id,
        division_ocdid=post.division_ocdid,
        role_label="Council Member",
        designations=designations,
    )


def test_a_post_carries_the_designations_of_every_membership_held_on_it():
    """An at-large post is one expected membership, however many seat markers its holders have."""
    at_large, mayor = _post("council-member"), _post("mayor")
    held = [_held(at_large, ["Seat 1"]), _held(at_large, ["Seat 2"]), _held(mayor, ["Seat 9"])]

    [council] = _post_memberships([at_large], held, _ROLE_CONFIG, _OCDID)

    assert council.designations == ["Seat 1", "Seat 2"]


# --- _researched_memberships: the first scrape, parsed with the shared parser ---

_DEFAULT = KnownOrganization(id="government", name="Government", meta_is_default=True, posts=[])
_OTHER = KnownOrganization(id="schools", name="School Board", posts=[])


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


def _person(
    person_id: str = "p",
    source_urls: list[str] | None = None,
    memberships: list[Membership] | None = None,
) -> Person:
    return Person(
        id=person_id,
        name="Someone",
        jurisdiction_ocdid=_OCDID,
        source_urls=source_urls or [],
        memberships=memberships or [],
    )


def _membership(organization_id: str, source_urls: list[str]) -> Membership:
    return Membership(
        post_id="post",
        organization_id=organization_id,
        role_id="council-member",
        division_ocdid=_BASE,
        role_label="Council Member",
        source_urls=source_urls,
    )


def test_only_membership_pages_seed_the_crawl():
    """A person's own `source_urls` span every organization they were ever seen in; the pages
    behind their memberships are the ones that belong to an organization."""
    seeds = _source_urls(
        _config(),
        [
            _person("a", ["https://zz.gov/news"], [_membership("council", ["https://zz.gov/council"])]),
            _person("b", ["https://zz.gov/news"]),
        ],
    )

    assert seeds == ["https://zz.gov/council"]


def test_a_one_person_organization_keeps_its_page():
    """A mayor's office page is seeded though nobody else was read from it."""
    seeds = _source_urls(
        _config(),
        [_person("a", [], [_membership("mayor", ["https://zz.gov/mayor"])])],
    )

    assert seeds == ["https://zz.gov/mayor"]


def test_the_directory_comes_before_the_bios_it_links_to():
    """Both are worth fetching; the roster page is worth fetching first."""
    directory = "https://zz.gov/council"
    people = [
        _person(name, [], [_membership("council", [directory, f"https://zz.gov/council/{name}"])])
        for name in ("ana", "ben", "cal")
    ]

    seeds = _source_urls(_config(), people)

    assert seeds[0] == directory
    assert sorted(seeds[1:]) == [f"https://zz.gov/council/{n}" for n in ("ana", "ben", "cal")]


def test_a_page_two_organizations_were_read_from_is_seeded_once():
    """A shared "elected officials" listing belongs to both, and the crawler fetches one page."""
    shared = "https://zz.gov/elected-officials"
    people = [
        _person("a", [], [_membership("council", [shared])]),
        _person("b", [], [_membership("mayor", [shared])]),
    ]

    seeds = _source_urls(_config(), people)

    assert seeds == [shared]


def test_a_configured_list_wins_over_everything():
    """A human naming the pages means they know something the last scrape did not."""
    seeds = _source_urls(
        _config(["https://zz.gov/only-this"]),
        [
            _person("a", ["https://zz.gov/council"]),
            _person("b", ["https://zz.gov/council"]),
        ],
    )

    assert seeds == ["https://zz.gov/only-this"]
