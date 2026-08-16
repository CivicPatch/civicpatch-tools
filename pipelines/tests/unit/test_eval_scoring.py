"""`failing_people` — the per-person diagnostic built from already-computed scores.

It replaced a ~300-line loop that reloaded saved output and re-scored it, i.e. a second
implementation of score_case. That copy had drifted: it carried a designation exemption
written as `d in ["district", "ward"]`, comparing a whole designation to a bare word, so it
never matched and those fields scored a permanent 1.0. Tests here so the replacement cannot
drift the same way.
"""

import pathlib
import sys

import pytest

pytestmark = pytest.mark.unit

EVALS = pathlib.Path("tests/prompts/tests/evals")


@pytest.fixture(scope="module", autouse=True)
def _eval_dir_on_path():
    path = str(EVALS.resolve())
    sys.path.insert(0, path)
    yield
    sys.path.remove(path)


def _person(name, scores, actual=None, expected=None):
    return {
        "person_name": name,
        "scores": scores,
        "actual": actual or {},
        "expected": expected or {},
    }


def test_reports_only_fields_below_their_floor():
    from scoring import failing_people

    rows = failing_people(
        {"case_a": [_person("Ann", {"name": 1.0, "phone": 0.0})]},
        {"name": 1.0, "phone": 1.0},
    )
    assert [r["field"] for r in rows] == ["phone"]
    assert rows[0]["case_id"] == "case_a" and rows[0]["person"] == "Ann"


def test_carries_the_values_needed_to_diagnose():
    from scoring import failing_people

    rows = failing_people(
        {"c": [_person("Ann", {"email": 0.0}, {"email": "a@x.com"}, {"email": "b@x.com"})]},
        {"email": 1.0},
    )
    assert rows[0]["expected"] == "b@x.com" and rows[0]["actual"] == "a@x.com"
    assert rows[0]["score"] == 0.0 and rows[0]["threshold"] == 1.0


def test_a_field_the_person_does_not_carry_is_not_a_failure():
    """Recall-only fields are omitted when nothing was expected. Treating an absent key as
    zero is what inflated those dimensions before."""
    from scoring import failing_people

    assert failing_people({"c": [_person("Ann", {"name": 1.0})]}, {"start_date": 1.0}) == []


def test_untracked_thresholds_are_ignored():
    from scoring import failing_people

    rows = failing_people({"c": [_person("Ann", {"name": 0.0, "phone": 0.0})]}, {"name": 1.0})
    assert [r["field"] for r in rows] == ["name"]


def test_orders_by_case_so_output_is_stable():
    from scoring import failing_people

    rows = failing_people(
        {"z": [_person("Z", {"name": 0.0})], "a": [_person("A", {"name": 0.0})]},
        {"name": 1.0},
    )
    assert [r["case_id"] for r in rows] == ["a", "z"]


def test_no_cases_yields_nothing():
    from scoring import failing_people

    assert failing_people({}, {"name": 1.0}) == []
