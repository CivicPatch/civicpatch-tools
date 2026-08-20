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


def _official(person_id, office_name, division_ocdid=None):
    return Official(
        id=person_id,
        name=f"Person {person_id}",
        office=Office(name=office_name, division_ocdid=division_ocdid),
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
def test_recognised_designations_do_not_split_a_post():
    """Position 1 and Position 2 share a post; the text rides on the memberships."""
    specs = derived_posts(
        [_official("a", "Council Member Position 1"), _official("b", "Council Member Position 2")],
        _TAXONOMY,
        _ROLES,
    )
    assert len(specs) == 1
    assert sorted(d for m in specs[0].members for d in m.designations) == ["Position 1", "Position 2"]


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
    assert [(m.person_id, m.unmatched_text) for m in specs[0].members] == [("a", ["Town Moderator"])]


@pytest.mark.unit
def test_at_large_with_no_value_is_swallowed_and_does_not_reach_the_residue():
    specs = derived_posts([_official("a", "Council Member At-Large")], _TAXONOMY, _ROLES)
    assert specs[0].division_ocdid == _BASE
    assert [(m.person_id, m.designations, m.unmatched_text) for m in specs[0].members] == [("a", [], [])]


@pytest.mark.unit
def test_the_records_own_division_beats_the_one_parsed_from_its_label():
    """Measured over the corpus: 2,824 published people carry a ward or district in
    `office.division_ocdid` against 57 whose label mentions one. Re-deriving from the label
    alone collapsed every ward seat in a town onto one at-large post."""
    specs = derived_posts(
        [
            _official("a", "Council Member", division_ocdid=f"{_BASE}/ward:1"),
            _official("b", "Council Member", division_ocdid=f"{_BASE}/ward:2"),
        ],
        _TAXONOMY,
        _ROLES,
    )
    assert len(specs) == 2
    assert {s.division_ocdid for s in specs} == {f"{_BASE}/ward:1", f"{_BASE}/ward:2"}


@pytest.mark.unit
def test_the_label_is_used_when_the_record_carries_no_division():
    specs = derived_posts([_official("a", "Council Member Ward 3")], _TAXONOMY, _ROLES)
    assert specs[0].division_ocdid == f"{_BASE}/ward:3"


# --- everything a scrape produces becomes a post -------------------------------------------
#
# The demotion pass that used to live here is gone: a hardcoded set of "jurisdiction-wide"
# role ids drifts from `roles`, which is DB-managed. If churn proves painful a maintainer
# blacklists the role from posts and it renders on the membership instead.

_WARD_3 = f"{_BASE}/council_district:3"
_WARD_5 = f"{_BASE}/council_district:5"


@pytest.mark.unit
def test_a_jurisdiction_wide_role_at_an_electoral_division_still_mints_its_own_post():
    specs = derived_posts(
        [
            _official("a", "Mayor", _WARD_3),
            _official("b", "Council Member", _WARD_5),
        ],
        _TAXONOMY,
        _ROLES,
    )
    by_role = _by_role(specs)

    assert by_role["mayor"].division_ocdid == _WARD_3
    assert by_role["council-member"].division_ocdid == _WARD_5


@pytest.mark.unit
def test_headcount_counts_holders_even_for_a_role_marked_unique():
    """`is_unique` no longer pins headcount to 1 — the count is what the page listed."""
    specs = derived_posts(
        [_official("a", "Mayor"), _official("b", "Mayor")], _TAXONOMY, _ROLES
    )

    assert len(specs) == 1
    assert specs[0].role_id == "mayor"
    assert specs[0].headcount == 2
