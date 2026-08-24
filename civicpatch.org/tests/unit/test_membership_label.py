"""Unit tests for the derived seat name (core.membership_label).

Pure — the fallback used when nobody has set `memberships.label`.
"""

import pytest

from core.membership_label import derive_label, proposed_membership_label

_WHOLE = "ocd-division/country:us/state:wa/place:seattle"
_D3 = f"{_WHOLE}/council_district:3"


@pytest.mark.unit
def test_a_plain_seat_is_just_its_role():
    assert derive_label("Mayor", _WHOLE, [], []) == "Mayor"


@pytest.mark.unit
def test_a_division_is_named_readably():
    assert derive_label("Council Member", _D3, [], []) == "Council Member, District 3"


@pytest.mark.unit
def test_designations_come_before_the_division():
    """"Position 8" is what tells two identical at-large seats apart — dropping it would
    render Seattle's two at-large councilmembers the same."""
    assert (
        derive_label("Council Member", _WHOLE, ["Position 8"], [])
        == "Council Member, Position 8"
    )


@pytest.mark.unit
def test_unmatched_text_is_shown_rather_than_hidden():
    """It came off the page. A label that silently omits it looks correct while losing what
    nobody could classify."""
    assert (
        derive_label("Trustee", _WHOLE, [], ["Zoning Administrator"])
        == "Trustee, Zoning Administrator"
    )


@pytest.mark.unit
def test_a_whole_government_division_adds_nothing():
    """`place:` and `county:` name a government, not a division of one."""
    county = "ocd-division/country:us/state:mi/county:chippewa/place:detour"
    assert derive_label("Mayor", county, [], []) == "Mayor"


# `proposed_membership_label` — the other half. `derive_label` reconstructs the *post's* name
# from structured fields; this says what belongs to the membership rather than to the post.
#
# The split is by level, not by whether the parser placed the text. Post-level pieces are never
# repeated: the winning role defines the post, a losing role rides along in `membership_roles`,
# and the division is the post's. Membership-level pieces are — non-division designations and
# residue the parse could not place, which are what tell two people on one post apart.


def _part(label: str, role: str | None, **extra):
    return {"label": label, "role": role, **extra}


@pytest.mark.unit
def test_a_membership_holding_only_the_post_says_nothing_extra():
    assert proposed_membership_label([_part("Council Member", "Council Member")]) is None


@pytest.mark.unit
def test_a_demoted_role_is_not_the_label_because_it_has_a_column():
    """Joy Hollingsworth's row. Seattle names her twice — "Councilmember District 3" and
    "Council President District 3" — so the presidency wins the post and `council-member` is
    written to `membership_roles` (130).

    Taking the losing part whole used to make the label "Councilmember District 3": a role
    already stored beside the membership, and a division the post itself carries. Every word
    of it was recorded somewhere else."""
    parts = [
        _part("Councilmember District 3", "Council Member"),
        _part("Council President District 3", "Council President"),
    ]

    assert proposed_membership_label(parts) is None


@pytest.mark.unit
def test_a_designation_is_the_label_because_nothing_else_shows_it():
    """"Council Member Seat 3" and "CouncilMember Seat 3" are one office said twice. The role
    goes up to the post, both spellings survive in `source_labels`, and `seat` names no
    division — so the post is at-large and "Seat 3" is the only thing distinguishing this
    membership from the next one on the same post."""
    parts = [
        _part("Council Member Seat 3", "Council Member", other_designations=["Seat 3"]),
        _part("CouncilMember Seat 3", "Council Member", other_designations=["Seat 3"]),
    ]

    assert proposed_membership_label(parts) == "Seat 3"


@pytest.mark.unit
def test_residue_the_parse_could_not_place_survives():
    """Kept here *and* in `unmatched_text`: the label says what the source called them, triage
    says we have no role for it. Different questions, different columns."""
    parts = [
        _part("Deputy Mayor", "Deputy Mayor"),
        _part("City Attorney", None, unmatched=["City Attorney"]),
    ]

    assert proposed_membership_label(parts) == "City Attorney"


@pytest.mark.unit
def test_a_qualifier_survives_even_when_its_part_won_the_post():
    """The case the residue half exists for. "Commissioner" is the post, so by role alone this
    part is redundant — but the post label is a reconstruction and cannot say "Of Public
    Safety"."""
    parts = [
        _part("Commissioner Of Public Safety", "Commissioner", unmatched=["Of Public Safety"])
    ]

    assert proposed_membership_label(parts) == "Of Public Safety"


@pytest.mark.unit
def test_designations_and_residue_read_in_source_order():
    """Daisy Palomo's row: Deputy Mayor Pro Tempore wins the post, "Council Member" is stored
    as a demoted role, and "Place 6" is the seat within the body."""
    parts = [
        _part("Council Member", "Council Member"),
        _part("Deputy Mayor Pro Tempore", "Deputy Mayor Pro Tempore"),
        # At-large with no value: consumed by the parser and recorded nowhere. It restates the
        # division every post already sits on.
        _part("At-Large", None),
        _part("Place 6", None, other_designations=["Place 6"]),
    ]

    assert proposed_membership_label(parts) == "Place 6"


@pytest.mark.unit
def test_the_same_designation_on_two_parts_is_said_once():
    """Two spellings of one office both parse to `Seat 3`; the label is what to show, not a
    tally of how many times the source said it."""
    parts = [
        _part("Council Member Seat 3", "Council Member", other_designations=["Seat 3"]),
        _part("Councilmember Seat 3", "Council Member", other_designations=["Seat 3"]),
    ]

    assert proposed_membership_label(parts) == "Seat 3"


@pytest.mark.unit
def test_nothing_parsed_yields_no_label():
    assert proposed_membership_label([]) is None
