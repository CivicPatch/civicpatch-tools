"""The derived seat name, and one person's label within it (core.membership_label).

Pure — the fallback used when nobody has set `memberships.label`.

`derive_label` split into two when `MembershipLabel` landed: `derive_post_label` names the
seat everyone in it shares, and `render(MembershipLabel(...))` adds what one occupant's own
labels carried past it. Four of the old function's five callers passed empty designations and
unmatched text — they had always wanted just the seat.
"""

import pytest

from core.membership_label import (
    MembershipLabel,
    derive_post_label,
    render,
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
def test_a_designation_follows_the_seat():
    """Was `test_designations_come_before_the_division`, which asserted the designation was
    interleaved into the seat's name. It now follows it: the seat is what every holder shares
    and stays contiguous, and "Position 8" is about one of them.

    "Position 8" is still what tells two identical at-large seats apart — dropping it would
    render Seattle's two at-large councilmembers the same."""
    assert (
        render(
            MembershipLabel(post_label="Council Member", designations=["Position 8"])
        )
        == "Council Member, Position 8"
    )


@pytest.mark.unit
def test_the_seat_stays_contiguous_before_the_occupants_own_parts():
    """The reason the order changed. `Council Member, District 5` is one seat named in two
    words; splitting a designation between them read as three separate things."""
    assert (
        render(
            MembershipLabel(
                post_label=derive_post_label("Council Member", _D3),
                designations=["Place 2"],
            )
        )
        == "Council Member, District 3, Place 2"
    )


@pytest.mark.unit
def test_a_demoted_role_is_named_after_the_seat():
    """Someone who is Mayor and also a Council Member holds one seat and is described by
    both. The losing role belongs to the occupant, not to the seat."""
    assert (
        render(MembershipLabel(post_label="Mayor", demoted_roles=["Council Member"]))
        == "Mayor, Council Member"
    )


@pytest.mark.unit
def test_unmatched_text_is_shown_rather_than_hidden():
    """It came off the page. A label that silently omits it looks correct while losing what
    nobody could classify."""
    assert (
        render(
            MembershipLabel(
                post_label="Trustee", unmatched_text=["Zoning Administrator"]
            )
        )
        == "Trustee, Zoning Administrator"
    )


@pytest.mark.unit
def test_a_whole_government_division_adds_nothing():
    """`place:` and `county:` name a government, not a division of one."""
    county = "ocd-division/country:us/state:mi/county:chippewa/place:detour"
    assert derive_post_label("Mayor", county) == "Mayor"

