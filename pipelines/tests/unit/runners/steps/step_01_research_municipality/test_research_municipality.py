"""What the scrape steers by, read off cp.org's posts.

These used to test `_roles_from_posts_from_db`, which split `office.name` on " - " and resolved
each part against the taxonomy. A post carries one decided `role_id`, so there is nothing to
split and nothing to resolve — the test for compound office names went with the splitting.
"""

import pytest

from runners.people_collector.steps.step_01_research_municipality.research_municipality import (
    _roles_from_posts,
    _parts_from_research,
    _divisions_from_posts,
)
from runners.people_collector.schemas import ResearchedPerson
from shared.schemas import Role, RoleConfig

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


def _post(role_id: str, division_ocdid: str = _BASE) -> dict:
    return {"role_id": role_id, "division_ocdid": division_ocdid}


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
