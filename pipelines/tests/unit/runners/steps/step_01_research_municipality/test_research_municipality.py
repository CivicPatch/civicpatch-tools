"""What the scrape steers by, read off cp.org's posts.

These used to test `_roles_from_posts_from_db`, which split `office.name` on " - " and resolved
each part against the taxonomy. A post carries one decided `role_id`, so there is nothing to
split and nothing to resolve — the test for compound office names went with the splitting.
"""

from types import SimpleNamespace

import pytest

from runners.people_collector.steps.step_01_research_municipality.research_municipality import (
    _roles_from_posts,
    _parts_from_research,
    _divisions_from_posts,
    _source_urls,
)
from runners.people_collector.schemas import ResearchedPerson
from shared.schemas import Membership, Person, Post, Role, RoleConfig

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


def test_a_posts_role_id_renders_as_its_taxonomy_label():
    roles = _roles_from_posts([_post("mayor"), _post("council-member")], _ROLE_CONFIG)
    assert roles == ["Mayor", "Council Member"]


def test_one_role_across_many_posts_is_named_once():
    """It becomes prompt keywords, so repeats are noise."""
    posts = [_post("council-member", f"{_BASE}/ward:{n}") for n in (1, 2, 3)]
    assert _roles_from_posts(posts, _ROLE_CONFIG) == ["Council Member"]


def test_a_role_the_config_does_not_name_is_skipped():
    """`unmatched` is a real post's role and has no label worth searching a page for."""
    assert _roles_from_posts([_post("unmatched"), _post("mayor")], _ROLE_CONFIG) == ["Mayor"]


def test_no_posts_means_nothing_to_look_for():
    assert _roles_from_posts([], _ROLE_CONFIG) == []
    assert _divisions_from_posts([], _OCDID) == []


def test_each_posts_division_becomes_the_designation_a_label_would_name():
    posts = [_post("council-member", f"{_BASE}/ward:1"), _post("council-member", f"{_BASE}/ward:2")]
    assert _divisions_from_posts(posts, _OCDID) == ["ward 1", "ward 2"]


def test_a_post_covering_the_whole_jurisdiction_is_no_target():
    """There is no ward to go looking for, so an at-large post sets no goal."""
    assert _divisions_from_posts([_post("mayor", _BASE)], _OCDID) == []


# --- _parts_from_research: the first scrape, split once with the shared parser ---


def _researched(label: str) -> ResearchedPerson:
    return ResearchedPerson(name="Ann Lee", label=label)


def test_a_researched_label_is_split_into_role_and_division():
    """The same `parse_label` cp.org runs at ingest, so a first scrape and every later one
    agree about what a label means."""
    roles, designations = _parts_from_research(
        [_researched("Council Member, Ward 3")], _ROLE_CONFIG
    )
    assert roles == ["Council Member"]
    assert designations == ["ward 3"]


def test_a_label_naming_no_division_sets_no_goal():
    roles, designations = _parts_from_research([_researched("Mayor")], _ROLE_CONFIG)
    assert roles == ["Mayor"]
    assert designations == []


def test_one_role_across_several_researched_people_is_named_once():
    roles, _ = _parts_from_research(
        [_researched("Council Member, Ward 1"), _researched("Council Member, Ward 2")],
        _ROLE_CONFIG,
    )
    assert roles == ["Council Member"]


def test_research_that_named_no_offices_steers_by_nothing():
    assert _parts_from_research([_researched("")], _ROLE_CONFIG) == ([], [])


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
