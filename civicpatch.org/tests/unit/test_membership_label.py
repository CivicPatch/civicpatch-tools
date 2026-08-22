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
# from structured fields; this takes the source's own words for what the post cannot say.
# Only `label` and `role` are read, so the fixtures carry just those.


def _part(label: str, role: str | None):
    return {"label": label, "role": role}


@pytest.mark.unit
def test_a_membership_holding_only_the_post_says_nothing_extra():
    parts = [_part("Council Member", "Council Member")]

    assert proposed_membership_label(parts, "Council Member") is None


@pytest.mark.unit
def test_the_demoted_office_becomes_the_label():
    """Deputy Mayor wins the post. "Commissioner Of Public Safety" is what the post cannot
    say, and the qualifier survives only because the part is taken whole."""
    parts = [
        _part("Commissioner Of Public Safety", "Commissioner"),
        _part("Deputy Mayor", "Deputy Mayor"),
    ]

    assert (
        proposed_membership_label(parts, "Deputy Mayor")
        == "Commissioner Of Public Safety"
    )


@pytest.mark.unit
def test_a_spelling_variant_of_the_post_role_is_not_leftover():
    """"President Pro Tem" resolves to the post's own role. Comparing labels instead would
    keep it, and the row would read as though the person held two offices."""
    parts = [
        _part("President Pro Tem", "President Pro Tempore"),
        _part("Council Member", "Council Member"),
    ]

    assert proposed_membership_label(parts, "President Pro Tempore") == "Council Member"


@pytest.mark.unit
def test_designations_and_demoted_roles_read_in_source_order():
    """Daisy Palomo's row: the post is Deputy Mayor Pro Tempore, and everything else the
    source said about her seat belongs to the membership."""
    parts = [
        _part("Council Member", "Council Member"),
        _part("Deputy Mayor Pro Tempore", "Deputy Mayor Pro Tempore"),
        # At-large with no value: consumed by the parser and recorded nowhere.
        {"label": "At-Large", "role": None},
        {"label": "Place 6", "role": None, "other_designations": ["Place 6"]},
    ]

    assert (
        proposed_membership_label(parts, "Deputy Mayor Pro Tempore")
        == "Council Member, Place 6"
    )


@pytest.mark.unit
def test_an_office_with_no_role_is_still_worth_showing():
    """Kept here *and* in `unmatched_text`: the label says what the source called them, triage
    says we have no role for it. Different questions, different columns."""
    parts = [
        _part("Deputy Mayor", "Deputy Mayor"),
        # An unresolved office is residue, which is what tells it from a bare "At-Large".
        {"label": "City Attorney", "role": None, "unmatched": ["City Attorney"]},
    ]

    assert proposed_membership_label(parts, "Deputy Mayor") == "City Attorney"


@pytest.mark.unit
def test_nothing_parsed_yields_no_label():
    assert proposed_membership_label([], None) is None


@pytest.mark.unit
def test_a_qualifier_survives_even_when_its_part_won_the_post():
    """The case the whole rule exists for. "Commissioner" is the post, so by role alone this
    part is redundant — but the post label is a reconstruction and cannot say "Of Public
    Safety". Dropping it here loses it entirely, since the residue no longer reaches triage.
    """
    parts = [
        {
            "label": "Commissioner Of Public Safety",
            "role": "Commissioner",
            "unmatched": ["Of Public Safety"],
        }
    ]

    assert (
        proposed_membership_label(parts, "Commissioner")
        == "Commissioner Of Public Safety"
    )


@pytest.mark.unit
def test_a_clean_part_that_won_the_post_is_still_dropped():
    """The other side: no residue means the post label already says everything."""
    parts = [{"label": "Commissioner", "role": "Commissioner", "unmatched": []}]

    assert proposed_membership_label(parts, "Commissioner") is None


@pytest.mark.unit
def test_a_bare_at_large_is_dropped():
    """It restates the division every post already sits on, so it is noise in a label whose
    whole job is saying what the post does not."""
    parts = [
        _part("Mayor", "Mayor"),
        {"label": "At-Large", "role": None},
    ]

    assert proposed_membership_label(parts, "Mayor") is None
