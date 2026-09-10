"""Batching a roster's worth of assertions.

A single save can state claims for several people at once — `roster_edits.py` builds one list of
`Assertion`s across the whole patched roster and writes it in one call. Written one at a time
that was two statements each, in series inside one transaction.
"""

import pytest

from database.assertions import latest_of_each
from schemas.assertions import Assertion, AssertionKind, EntityType

pytestmark = pytest.mark.unit


def _claim(field: str, value, kind=AssertionKind.ACCEPT, entity="p1") -> Assertion:
    return Assertion(
        entity_type=EntityType.PERSON,
        entity_id=entity,
        field_path=field,
        kind=kind,
        value=value,
    )


def test_a_scalar_field_answered_twice_keeps_the_last_answer():
    """`_REPLACES_THE_FIELD` keys on the field alone, so both claims are the same row. Sending
    both would have the second overwrite the first anyway — this makes that the rule rather
    than an accident of ordering."""
    claims = [_claim("name", "Nancy Backus"), _claim("name", "Nancy J. Backus")]

    assert [c.value for c in latest_of_each(claims)] == ["Nancy J. Backus"]


def test_two_values_of_one_list_field_are_both_kept():
    """`phones` keys on the value, so two numbers are two rows, not a contradiction."""
    claims = [_claim("phones", "(253) 931-3041"), _claim("phones", "(253) 931-3042")]

    assert len(latest_of_each(claims)) == 2


def test_the_same_list_value_twice_collapses():
    claims = [_claim("phones", "(253) 931-3041")] * 2

    assert len(latest_of_each(claims)) == 1


def test_accepting_and_rejecting_one_list_value_keeps_only_the_later_word():
    """Not a quirk of this function — the database cannot hold both. `_REPLACES_THE_VALUE` is
    keyed `(entity_type, entity_id, field_path, value)` and its predicate covers rejects *and*
    every list field, so `kind` is not part of the key: the two claims are one index row, which
    is why `_DROP_THE_OPPOSITE` exists at all. Last word wins, either way round."""
    accept = _claim("phones", "(253) 931-3041")
    reject = _claim("phones", "(253) 931-3041", kind=AssertionKind.REJECT)

    assert [c.kind for c in latest_of_each([accept, reject])] == [AssertionKind.REJECT]
    assert [c.kind for c in latest_of_each([reject, accept])] == [AssertionKind.ACCEPT]


def test_accepting_and_rejecting_a_scalar_are_separate_rows():
    """A scalar accept keys on the field, a reject on the value — different predicates, so
    unlike the list case above these are two rows and both survive."""
    claims = [
        _claim("name", "Nancy Backus"),
        _claim("name", "Nancy Backus", kind=AssertionKind.REJECT),
    ]

    assert len(latest_of_each(claims)) == 2


def test_two_people_answering_the_same_field_are_not_collapsed():
    claims = [_claim("name", "Ann", entity="p1"), _claim("name", "Bo", entity="p2")]

    assert len(latest_of_each(claims)) == 2


def test_nothing_in_nothing_out():
    assert latest_of_each([]) == []
