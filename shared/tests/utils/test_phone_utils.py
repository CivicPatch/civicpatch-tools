"""Both functions are total: a string or None, never an exception.

The totality is the point, not a detail. While `normalize_phone_number` signalled failure
two ways, the pipeline's retry guard wrapped only the exception — so an invalid-but-parseable
number like `555-555-5555` was accepted and re-reading the page was never triggered.
"""

import pytest
from shared.utils import phone_utils

# Parseable but not real numbers. These are the ones that used to slip through, so they are
# the reason this module is total — keep them.
INVALID_BUT_PARSEABLE = ["123-4567", "555-555-5555", "000-000-0000"]

UNPARSEABLE = ["not a phone number", "1", "abc", "()"]


# normalize_phone_number


def test_canonicalizes_to_us_national_format():
    assert phone_utils.normalize_phone_number("856-358-2509") == "(856) 358-2509"


@pytest.mark.parametrize("layout", ["8563582509", "(856) 358-2509", "+1 856 358 2509"])
def test_accepts_any_layout(layout):
    assert phone_utils.normalize_phone_number(layout) == "(856) 358-2509"


@pytest.mark.parametrize("phone", INVALID_BUT_PARSEABLE)
def test_invalid_but_parseable_returns_none(phone):
    assert phone_utils.normalize_phone_number(phone) is None


@pytest.mark.parametrize("phone", UNPARSEABLE)
def test_unparseable_returns_none_rather_than_raising(phone):
    """It raised before. Callers read the exception as *the* failure path and missed the
    None one, which is the bug this contract change fixes."""
    assert phone_utils.normalize_phone_number(phone) is None


@pytest.mark.parametrize("empty", ["", None])
def test_empty_returns_none(empty):
    """Was `""` for the empty string — a third outcome, and falsy like None, so no caller
    ever distinguished them."""
    assert phone_utils.normalize_phone_number(empty) is None


# A compound cell is rejected, not repaired


@pytest.mark.parametrize(
    "compound", ["856-358-2509 or 856-358-4010 Ext. 112", "856-358-2509 / 856-358-4010"]
)
def test_two_numbers_in_one_string_is_not_a_phone_number(compound):
    """`normalize_first_phone` used to return the first of these. It was repairing a
    contract violation — the prompt asks for one number and says which to prefer — and
    dropping the second on the floor to do it."""
    assert phone_utils.normalize_phone_number(compound) is None


@pytest.mark.parametrize(
    "phone,expected",
    [
        ("856-358-2509 ext. 22", "(856) 358-2509 ext. 22"),
        ("(856) 358-2509 x22", "(856) 358-2509 ext. 22"),
        ("Phone: 856-358-2509", "(856) 358-2509"),
    ],
)
def test_extensions_and_labels_still_pass(phone, expected):
    """Strictness has to land between "two numbers" and "one number written loosely"."""
    assert phone_utils.normalize_phone_number(phone) == expected
