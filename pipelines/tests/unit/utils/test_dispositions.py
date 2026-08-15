import pytest

from utils.dispositions import (
    Disposition,
    classify_membership,
    classify_value,
    tally,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "actual, expected, want",
    [
        ("a@x.com", "a@x.com", Disposition.correct),
        ("a@x.com", "b@x.com", Disposition.wrong_match),
        # The distinction recall could not draw: omitting a wanted value versus
        # inventing one that was not wanted.
        (None, "a@x.com", Disposition.false_negative),
        ("a@x.com", None, Disposition.false_positive),
        (None, None, None),
        # Empty string is absence, not a value — fixtures use both for "no value".
        ("", "", None),
        ("", "a@x.com", Disposition.false_negative),
    ],
)
def test_classify_value(actual, expected, want):
    assert classify_value(actual, expected) is want


def test_classify_value_uses_supplied_equality():
    same_number = lambda a, b: a.replace("-", "") == b.replace("-", "")
    assert classify_value("512-978-2100", "5129782100") is Disposition.wrong_match
    assert (
        classify_value("512-978-2100", "5129782100", equals=same_number)
        is Disposition.correct
    )


def test_classify_membership_counts_extras_and_omissions():
    got = classify_membership(["ann", "bob", "cid"], ["ann", "bob", "dee"])
    assert tally(got).model_dump() == {
        "correct": 2,
        "false_negative": 1,  # dee was wanted and not produced
        "false_positive": 1,  # cid was produced and not wanted
        "wrong_match": 0,
    }


def test_membership_never_yields_wrong_match():
    got = classify_membership(["x"], ["y"])
    assert Disposition.wrong_match not in got


def test_tally_precision_recall_f1():
    t = tally(
        [Disposition.correct] * 6
        + [Disposition.false_positive] * 2
        + [Disposition.false_negative] * 2
    )
    assert t.produced == 8 and t.wanted == 8
    assert t.precision == 0.75
    assert t.recall == 0.75
    assert t.f1 == 0.75


def test_wrong_match_counts_against_both_sides():
    """A disagreement is simultaneously a bad answer and a missed one, so it must land in
    both denominators — otherwise a model that answers everything wrongly scores 1.0."""
    t = tally([Disposition.wrong_match] * 4)
    assert t.produced == 4 and t.wanted == 4
    assert t.precision == 0.0 and t.recall == 0.0


def test_producing_nothing_scores_zero_not_undefined():
    """The case a gate must not let through: 12 values wanted, none produced. Precision is
    undefined there, so deriving F1 from it returns None and any `is not None` guard skips
    the worst possible result."""
    t = tally([Disposition.false_negative] * 12)
    assert t.precision is None
    assert t.recall == 0.0
    assert t.f1 == 0.0


def test_f1_is_none_only_when_nothing_was_compared():
    assert tally([]).f1 is None
    assert tally([None, None]).f1 is None


def test_tally_ignores_true_negatives():
    t = tally([None, None, Disposition.correct])
    assert t.correct == 1 and t.produced == 1 and t.wanted == 1


def test_rates_are_none_when_no_denominator():
    t = tally([])
    assert t.precision is None and t.recall is None and t.f1 is None
