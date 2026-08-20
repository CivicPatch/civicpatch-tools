"""Unit tests for the derived seat name (core.membership_label).

Pure — the fallback used when nobody has set `memberships.label`.
"""

import pytest

from core.membership_label import derive_label

_WHOLE = "ocd-division/country:us/state:wa/place:seattle"
_D3 = f"{_WHOLE}/council_district:3"


@pytest.mark.unit
def test_a_plain_seat_is_just_its_role():
    assert derive_label("Mayor", _WHOLE, [], []) == "Mayor"


@pytest.mark.unit
def test_a_division_is_named_readably():
    assert derive_label("Council Member", _D3, [], []) == "Council Member · District 3"


@pytest.mark.unit
def test_designations_come_before_the_division():
    """"Position 8" is what tells two identical at-large seats apart — dropping it would
    render Seattle's two at-large councilmembers the same."""
    assert (
        derive_label("Council Member", _WHOLE, ["Position 8"], [])
        == "Council Member · Position 8"
    )


@pytest.mark.unit
def test_unmatched_text_is_shown_rather_than_hidden():
    """It came off the page. A label that silently omits it looks correct while losing what
    nobody could classify."""
    assert (
        derive_label("Trustee", _WHOLE, [], ["Zoning Administrator"])
        == "Trustee · Zoning Administrator"
    )


@pytest.mark.unit
def test_a_whole_government_division_adds_nothing():
    """`place:` and `county:` name a government, not a division of one."""
    county = "ocd-division/country:us/state:mi/county:chippewa/place:detour"
    assert derive_label("Mayor", county, [], []) == "Mayor"
