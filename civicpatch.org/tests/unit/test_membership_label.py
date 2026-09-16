"""The derived seat name, and one person's label within it (core.membership_label).

Pure — the fallback used when nobody has set `memberships.label`.

`derive_post_label` names the seat everyone in it shares; `render(MembershipLabel(...))` names
what one occupant's own labels said beyond it. The two used to compose into one string here,
seat first — reversed because every caller already has the seat's name separately (the post it
belongs to), and every consumer of `render`'s output shows the two beside each other rather
than needing one glued string.
"""

import pytest

from core.membership_label import (
    MembershipLabel,
    derive_post_label,
    render,
    render_with_post_label,
)

_WHOLE = "ocd-division/country:us/state:wa/place:seattle"
_D3 = f"{_WHOLE}/council_district:3"


@pytest.mark.unit
def test_a_plain_seat_is_just_its_role():
    assert derive_post_label("Mayor", _WHOLE) == "Mayor"


@pytest.mark.unit
def test_a_division_is_named_readably():
    assert derive_post_label("Council Member", _D3) == "Council Member, District 3"


@pytest.mark.unit
def test_a_whole_government_division_adds_nothing():
    """`place:` and `county:` name a government, not a division of one."""
    county = "ocd-division/country:us/state:mi/county:chippewa/place:detour"
    assert derive_post_label("Mayor", county) == "Mayor"


@pytest.mark.unit
def test_nothing_beyond_the_seat_renders_empty():
    """The common case: nobody's own labels said anything the post's own name does not
    already cover."""
    assert render(MembershipLabel()) == ""


@pytest.mark.unit
def test_a_designation_stands_on_its_own():
    """ "Position 8" is still what tells two identical at-large seats apart — the seat's own
    name is shown beside this now, not folded into it, so this is just the designation."""
    assert render(MembershipLabel(designations=["Position 8"])) == "Position 8"


@pytest.mark.unit
def test_a_demoted_role_comes_before_a_designation():
    """Someone who is Mayor and also a Council Member holds one seat and is described by
    both. The losing role belongs to the occupant, so it renders here, not on the seat."""
    assert (
        render(
            MembershipLabel(demoted_roles=["Council Member"], designations=["Position 8"])
        )
        == "Council Member, Position 8"
    )


@pytest.mark.unit
def test_unmatched_text_is_shown_rather_than_hidden():
    """It came off the page. A label that silently omits it looks correct while losing what
    nobody could classify."""
    assert (
        render(MembershipLabel(meta_unmatched_text=["Zoning Administrator"]))
        == "Zoning Administrator"
    )


@pytest.mark.unit
def test_render_with_post_label_puts_the_seat_first():
    """`batch_review.py`'s only remaining use of the self-contained form: a dense multi-town
    table with no separate place to show the seat's own name."""
    assert (
        render_with_post_label(
            "Council Member, District 5", MembershipLabel(designations=["Chair"])
        )
        == "Council Member, District 5, Chair"
    )


@pytest.mark.unit
def test_render_with_post_label_is_just_the_seat_when_there_is_nothing_beyond_it():
    assert render_with_post_label("Mayor", MembershipLabel()) == "Mayor"

