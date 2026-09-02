"""Unit tests for the pure half of post derivation — Officials in, post derived out.

No database: this module decides *what* posts a scrape implies, and the SQL that writes them
is covered by tests/integration/database/test_post_derivation.py.
"""

import pytest

from core.post_derivation import UNMATCHED_ROLE_ID, ChosenPost, derived_posts
from shared.schemas import OpenStatesRecord, Role, RoleConfig, RoleStatus
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
    _role("commissioner", "Commissioner", priority=300),
]
_TAXONOMY = build_taxonomy(RoleConfig(roles=_ROLES))


def _person(person_id, office_name):
    """A roster row. A human's answers arrive separately, in `chosen_posts`.

    The fixtures pass one " - " string because it is compact to write; it is split here, so the
    join being retired happens once in a helper rather than on every record.
    """
    return OpenStatesRecord(
        id=person_id,
        name=person_id,
        jurisdiction_ocdid=_OCDID,
        source_urls=["https://example.gov"],
        updated_at="2026-01-01T00:00:00+00:00",
        labels=[part.strip() for part in office_name.split(" - ") if part.strip()],
    )


def _by_role(derived):
    return {post.role_id: post for post in derived}


@pytest.mark.unit
def test_one_spec_per_role_and_division():
    derived = derived_posts(
        [_person("a", "Mayor"), _person("b", "Council Member Ward 1")],
        _TAXONOMY,
        _ROLES,
    )
    assert {(post.role_id, post.division_ocdid) for post in derived} == {
        ("mayor", _BASE),
        ("council-member", f"{_BASE}/ward:1"),
    }


@pytest.mark.unit
def test_same_role_and_division_is_one_post_with_a_headcount():
    """The undifferentiated case: nothing separates them, so they share a post."""
    derived = derived_posts(
        [_person(x, "Council Member") for x in ("a", "b", "c")], _TAXONOMY, _ROLES
    )
    assert len(derived) == 1
    assert derived[0].headcount == 3
    assert len(derived[0].members) == 3


@pytest.mark.unit
def test_recognised_designations_do_not_split_a_post():
    """Position 1 and Position 2 share a post; the text rides on the memberships."""
    derived = derived_posts(
        [_person("a", "Council Member Position 1"), _person("b", "Council Member Position 2")],
        _TAXONOMY,
        _ROLES,
    )
    assert len(derived) == 1
    assert sorted(d for m in derived[0].members for d in m.designations) == ["Position 1", "Position 2"]


@pytest.mark.unit
def test_a_ward_splits_a_post_because_the_division_differs():
    derived = derived_posts(
        [_person("a", "Council Member Ward 1"), _person("b", "Council Member Ward 2")],
        _TAXONOMY,
        _ROLES,
    )
    assert len(derived) == 2
    assert all(spec.headcount == 1 for spec in derived)


@pytest.mark.unit
def test_an_unresolvable_label_lands_on_the_unmatched_role():
    """Nobody is postless — the residue carries what we could not place."""
    derived = derived_posts([_person("a", "Town Moderator")], _TAXONOMY, _ROLES)
    assert derived[0].role_id == UNMATCHED_ROLE_ID
    assert [(m.person_id, m.unmatched_text) for m in derived[0].members] == [("a", ["Town Moderator"])]


@pytest.mark.unit
def test_at_large_with_no_value_is_swallowed_and_does_not_reach_the_residue():
    derived = derived_posts([_person("a", "Council Member At-Large")], _TAXONOMY, _ROLES)
    assert derived[0].division_ocdid == _BASE
    assert [(m.person_id, m.designations, m.unmatched_text) for m in derived[0].members] == [("a", [], [])]


@pytest.mark.unit
def test_a_pick_keeps_ward_seats_from_collapsing_onto_one_at_large_post():
    """The same guarantee through the other channel: two bare "Council Member" labels, kept
    apart by the picks rather than by the record's own division."""
    derived = derived_posts(
        [_person("a", "Council Member"), _person("b", "Council Member")],
        _TAXONOMY,
        _ROLES,
        {
            "a": ChosenPost(role_id="council-member", division_ocdid=f"{_BASE}/ward:1"),
            "b": ChosenPost(role_id="council-member", division_ocdid=f"{_BASE}/ward:2"),
        },
    )
    assert len(derived) == 2
    assert {post.division_ocdid for post in derived} == {f"{_BASE}/ward:1", f"{_BASE}/ward:2"}


@pytest.mark.unit
def test_without_a_pick_a_bare_label_derives_one_at_large_post():
    """The other half of the claim above: unpicked, the two collapse. Correct — the source
    said nothing about wards — and the reason a pick is the only way to tell them apart."""
    derived = derived_posts(
        [_person("a", "Council Member"), _person("b", "Council Member")],
        _TAXONOMY,
        _ROLES,
    )
    assert len(derived) == 1
    assert derived[0].division_ocdid == _BASE


@pytest.mark.unit
def test_the_label_is_used_when_the_record_carries_no_division():
    derived = derived_posts([_person("a", "Council Member Ward 3")], _TAXONOMY, _ROLES)
    assert derived[0].division_ocdid == f"{_BASE}/ward:3"


# --- everything a scrape produces becomes a post -------------------------------------------
#
# The demotion pass that used to live here is gone: a hardcoded set of "jurisdiction-wide"
# role ids drifts from `roles`, which is DB-managed. If churn proves painful a maintainer
# blacklists the role from posts and it renders on the membership instead.

_WARD_3 = f"{_BASE}/council_district:3"
_WARD_5 = f"{_BASE}/council_district:5"


@pytest.mark.unit
def test_a_jurisdiction_wide_role_at_an_electoral_division_still_mints_its_own_post():
    derived = derived_posts(
        [_person("a", "Mayor"), _person("b", "Council Member")],
        _TAXONOMY,
        _ROLES,
        {
            "a": ChosenPost(role_id="mayor", division_ocdid=_WARD_3),
            "b": ChosenPost(role_id="council-member", division_ocdid=_WARD_5),
        },
    )
    by_role = _by_role(derived)

    assert by_role["mayor"].division_ocdid == _WARD_3
    assert by_role["council-member"].division_ocdid == _WARD_5


@pytest.mark.unit
def test_headcount_counts_holders_even_for_a_role_marked_unique():
    """`is_unique` no longer pins headcount to 1 — the count is what the page listed."""
    derived = derived_posts(
        [_person("a", "Mayor"), _person("b", "Mayor")], _TAXONOMY, _ROLES
    )

    assert len(derived) == 1
    assert derived[0].role_id == "mayor"
    assert derived[0].headcount == 2


@pytest.mark.unit
def test_the_losing_roles_are_demoted_onto_the_member_not_dropped():
    """One open membership per person per body means one role has to define the post. The
    others used to be parsed, ranked and then discarded — a councilmember who is also mayor
    published as a mayor and forgot the council seat entirely."""
    derived = derived_posts(
        [_person("p1", "Mayor - Council Member")], _TAXONOMY, _ROLES
    )

    by_role = _by_role(derived)
    # Mayor is priority 10 against Council Member's 500, so it defines the post.
    assert list(by_role) == ["mayor"]
    assert by_role["mayor"].members[0].role_ids == ["council-member"]


@pytest.mark.unit
def test_every_losing_role_is_kept_not_just_the_first():
    """The corpus has labels naming five roles — "Chair - Chair Pro Tem - Vice Mayor - Council
    President - Council Member". A singular column kept one and dropped the rest."""
    # Order is the ranking: `build_taxonomy` ranks by position in the list, and `get_roles`
    # returns them already sorted by `priority`. Appending would make these rank last.
    roles = [
        _role("mayor", "Mayor", priority=10, is_unique=True),
        _role("chair", "Chair", priority=200, is_unique=True),
        _role("vice-chair", "Vice Chair", priority=300, is_unique=True),
        _role("council-member", "Council Member", ["Councilmember"], priority=500),
    ]
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    derived = derived_posts(
        [_person("p1", "Chair - Vice Chair - Council Member")], taxonomy, roles
    )

    by_role = _by_role(derived)
    assert list(by_role) == ["chair"]
    assert by_role["chair"].members[0].role_ids == ["vice-chair", "council-member"]


@pytest.mark.unit
def test_a_single_role_demotes_nothing():
    """The common case. A demoted role on an ordinary label would be noise on every row."""
    derived = derived_posts([_person("p1", "Council Member")], _TAXONOMY, _ROLES)

    assert derived[0].members[0].role_ids == []


@pytest.mark.unit
def test_a_second_role_the_taxonomy_does_not_know_is_not_demoted():
    """`membership_roles.role_id` is a foreign key, so a role with no id has nowhere to go —
    it stays in `unmatched_text`, where triage can act on it."""
    derived = derived_posts(
        [_person("p1", "Council Member - Harbormaster")], _TAXONOMY, _ROLES
    )

    member = derived[0].members[0]
    assert member.role_ids == []
    assert "Harbormaster" in member.unmatched_text


@pytest.mark.unit
def test_the_member_label_says_what_the_post_label_cannot():
    """Mayor (10) wins the post. "Commissioner" alone would be in `role_ids` already, but the
    portfolio only survives because the whole source part is kept verbatim."""
    derived = derived_posts(
        [_person("a", "Commissioner Of Public Safety - Mayor")], _TAXONOMY, _ROLES
    )

    member = derived[0].members[0]
    assert derived[0].role_id == "mayor"
    assert member.label == "Of Public Safety"


@pytest.mark.unit
def test_a_member_holding_only_the_post_proposes_no_label():
    derived = derived_posts([_person("a", "Council Member")], _TAXONOMY, _ROLES)

    assert derived[0].members[0].label is None


@pytest.mark.unit
def test_residue_of_a_resolved_label_is_not_unmatched():
    """"Of Public Safety" came out of a label that resolved to Commissioner. There is no rule
    a curator could add for it, so it must not reach triage — the label carries it instead.

    The role itself does not: `commissioner` defines the post here, and a label repeating it
    would say the same thing twice."""
    derived = derived_posts(
        [_person("a", "Commissioner Of Public Safety")], _TAXONOMY, _ROLES
    )

    member = derived[0].members[0]
    assert member.unmatched_text == []
    assert member.label == "Of Public Safety"


@pytest.mark.unit
def test_a_part_that_resolved_to_nothing_still_reaches_triage():
    """The other side of the same rule: "Dogcatcher" names no role we know, which is exactly
    the vocabulary gap `unmatched_text` exists to collect."""
    derived = derived_posts([_person("a", "Mayor - Dogcatcher")], _TAXONOMY, _ROLES)

    assert derived[0].members[0].unmatched_text == ["Dogcatcher"]


@pytest.mark.unit
def test_a_chosen_post_decides_where_the_person_lands():
    """A human picked the post. Re-deriving it from the label could only disagree — and the
    label is what they were correcting."""
    person = _person("a", "Councilmember")
    # Keyed on the person: a pick is a human's answer and no longer rides on the record.
    chosen = {"a": ChosenPost(role_id="mayor", division_ocdid=_WARD_3)}

    derived = derived_posts([person], _TAXONOMY, _ROLES, chosen)

    assert [(spec.role_id, spec.division_ocdid) for spec in derived] == [("mayor", _WARD_3)]


@pytest.mark.unit
def test_a_chosen_post_does_not_rewrite_what_the_source_said():
    """The pick says where they serve. Designations, demoted roles and residue still come from
    the labels, because a post is not a claim about what the page called them."""
    person = _person("a", "Council Member - Place 6")
    # Picked onto the mayor's post, though the label says council member.
    chosen = {"a": ChosenPost(role_id="mayor", division_ocdid=_BASE)}

    member = derived_posts([person], _TAXONOMY, _ROLES, chosen)[0].members[0]

    assert member.source_labels == ["Council Member", "Place 6"]
    # "Place 6" is a designation, so it stays on the membership; `council-member` is a role
    assert member.label == "Place 6"


@pytest.mark.unit
def test_an_unknown_post_id_falls_back_to_the_parse():
    """A pick pointing at a post that no longer exists is not a reason to lose the person.

    `chosen_posts` drops it — a post it cannot resolve is simply absent — so the derivation sees
    no entry for this person and falls back to the label."""
    person = _person("a", "Mayor")

    derived = derived_posts([person], _TAXONOMY, _ROLES, {})

    assert [spec.role_id for spec in derived] == ["mayor"]
