"""Unit tests for the pure half of post derivation — Officials in, post specs out.

No database: this module decides *what* posts a scrape implies, and the SQL that writes them
is covered by tests/integration/database/test_post_derivation.py.
"""

import pytest

from core.post_derivation import UNMATCHED_ROLE_ID, derived_posts
from shared.schemas import Official, Office, Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:testville/government"
_BASE = "ocd-division/country:us/state:zz/place:testville"


def _role(id_, label, aliases=(), priority=500, is_unique=False):
    return Role(
        id=id_,
        label=label,
        status=RoleStatus.ACTIVE,
        aliases=list(aliases),
        priority=priority,
        is_unique=is_unique,
    )


_ROLES = [
    _role("mayor", "Mayor", priority=10, is_unique=True),
    _role("council-member", "Council Member", ["Councilmember"], priority=500),
]
_TAXONOMY = build_taxonomy(RoleConfig(roles=_ROLES))


def _official(person_id, office_name):
    return Official(
        id=person_id,
        name=f"Person {person_id}",
        office=Office(name=office_name),
        jurisdiction_ocdid=_OCDID,
        source_urls=["https://example.gov/council"],
        updated_at="2026-03-11T00:00:00+00:00",
    )


def _by_role(specs):
    return {spec.role_id: spec for spec in specs}


@pytest.mark.unit
def test_one_spec_per_role_and_division():
    specs = derived_posts(
        [_official("a", "Mayor"), _official("b", "Council Member Ward 1")],
        _TAXONOMY,
        _ROLES,
    )
    assert {(s.role_id, s.division_ocdid) for s in specs} == {
        ("mayor", _BASE),
        ("council-member", f"{_BASE}/ward:1"),
    }


@pytest.mark.unit
def test_same_role_and_division_is_one_post_with_a_headcount():
    """The undifferentiated case: nothing separates them, so they share a post."""
    specs = derived_posts(
        [_official(x, "Council Member") for x in ("a", "b", "c")], _TAXONOMY, _ROLES
    )
    assert len(specs) == 1
    assert specs[0].headcount == 3
    assert len(specs[0].members) == 3


@pytest.mark.unit
def test_a_unique_role_keeps_headcount_one_even_with_two_holders():
    """Two mayors is a data error to flag, not a two-seat office to invent."""
    specs = derived_posts([_official("a", "Mayor"), _official("b", "Mayor")], _TAXONOMY, _ROLES)
    assert _by_role(specs)["mayor"].headcount == 1
    assert len(_by_role(specs)["mayor"].members) == 2


@pytest.mark.unit
def test_recognised_designations_do_not_split_a_post():
    """Position 1 and Position 2 share a post; the text rides on the memberships."""
    specs = derived_posts(
        [_official("a", "Council Member Position 1"), _official("b", "Council Member Position 2")],
        _TAXONOMY,
        _ROLES,
    )
    assert len(specs) == 1
    assert sorted(residue for _, residue in specs[0].members) == ["Position 1", "Position 2"]


@pytest.mark.unit
def test_a_ward_splits_a_post_because_the_division_differs():
    specs = derived_posts(
        [_official("a", "Council Member Ward 1"), _official("b", "Council Member Ward 2")],
        _TAXONOMY,
        _ROLES,
    )
    assert len(specs) == 2
    assert all(spec.headcount == 1 for spec in specs)


@pytest.mark.unit
def test_an_unresolvable_label_lands_on_the_unmatched_role():
    """Nobody is postless — the residue carries what we could not place."""
    specs = derived_posts([_official("a", "Town Moderator")], _TAXONOMY, _ROLES)
    assert specs[0].role_id == UNMATCHED_ROLE_ID
    assert specs[0].members == [("a", "Town Moderator")]


@pytest.mark.unit
def test_at_large_with_no_value_is_swallowed_and_does_not_reach_the_residue():
    specs = derived_posts([_official("a", "Council Member At-Large")], _TAXONOMY, _ROLES)
    assert specs[0].division_ocdid == _BASE
    assert specs[0].members == [("a", None)]
