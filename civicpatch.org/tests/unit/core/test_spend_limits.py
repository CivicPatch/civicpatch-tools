"""Which cap a month's spend has reached. Pure, so no mocks."""

from decimal import Decimal

import pytest

from core.spend_limits import Cap, cap_reached

pytestmark = pytest.mark.unit


def test_nothing_is_reached_when_neither_cap_is_set():
    """The default everywhere: an unconfigured state under an unconfigured fleet."""
    assert cap_reached(Decimal("99"), None, Decimal("99"), None) is None


def test_a_state_over_its_own_cap_is_named_rather_than_just_flagged():
    verdict = cap_reached(Decimal("12"), Decimal("10"), Decimal("12"), Decimal("500"))
    assert verdict == Cap.STATE_MONTH


def test_a_state_under_its_cap_still_stops_when_the_global_one_is_spent():
    """The global cap is a shared cap — a state with room left still cannot draw from an
    empty pool."""
    verdict = cap_reached(Decimal("1"), Decimal("10"), Decimal("500"), Decimal("500"))
    assert verdict == Cap.GLOBAL_MONTH


def test_the_state_is_named_first_when_both_are_reached():
    """It is the narrower fix. Naming the global one first sends an operator to change a number
    that would not release this state anyway."""
    verdict = cap_reached(Decimal("10"), Decimal("10"), Decimal("500"), Decimal("500"))
    assert verdict == Cap.STATE_MONTH


def test_a_cap_of_zero_is_reached_before_anything_is_spent():
    """`$0` is a real setting meaning spend nothing, and this is what makes it a stop switch.
    A falsy check would read it as unset and let the state spend freely."""
    assert cap_reached(Decimal("0"), Decimal("0"), Decimal("0"), None) == Cap.STATE_MONTH


def test_spending_up_to_but_not_over_a_cap_is_still_allowed():
    assert cap_reached(Decimal("9.99"), Decimal("10"), Decimal("0"), None) is None
