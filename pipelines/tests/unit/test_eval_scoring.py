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


# --- label decomposition ---
#
# The model returns one record per label now, so a person holding two offices arrives as two
# records sharing a name, and the three set dimensions are derived from the label rather
# than read off the record.


def _record(name, label, **fields):
    from runners.people_collector.schemas import ExtractedPerson

    return ExtractedPerson(name=name, label=label, **fields)


def _dispositions(actual, expected):
    from accuracy import case_dispositions
    from scoring import EVAL_TAXONOMY

    return case_dispositions(actual, expected, EVAL_TAXONOMY)


def test_both_labels_of_a_two_office_person_are_scored():
    """A `{name: person}` lookup keeps only the last record, silently dropping a label."""
    records = [
        _record("Sharlene T. Hetzel", "Council Member Place 2 (West Ward)"),
        _record("Sharlene T. Hetzel", "Mayor Pro-Tem"),
    ]
    found = _dispositions(records, records)
    assert len(found["person"]) == 1
    assert [d.value for d in found["roles"]] == ["correct", "correct"]


def test_a_dropped_second_label_is_a_missing_role():
    expected = [
        _record("Sharlene T. Hetzel", "Council Member Place 2 (West Ward)"),
        _record("Sharlene T. Hetzel", "Mayor Pro-Tem"),
    ]
    found = _dispositions(expected[:1], expected)
    assert sorted(d.value for d in found["roles"]) == ["correct", "false_negative"]


def test_a_label_naming_two_offices_yields_both_roles():
    """Was: a merged label cost a `roles` miss. Now one label per person is the contract, so
    a second office lives inside the same string and both roles must come out of it — the
    published one being the highest-priority."""
    merged = [
        _record("Sharlene T. Hetzel", "Council Member Place 2 (West Ward) and Mayor Pro-Tem")
    ]
    found = _dispositions(merged, merged)
    assert [d.value for d in found["primary_role"]] == ["correct"]
    assert sorted(d.value for d in found["roles"]) == ["correct", "correct"]
    assert [d.value for d in found["district"]] == ["correct"]
    assert [d.value for d in found["designations_other"]] == ["correct"]


def test_primary_role_is_the_highest_priority_one_not_the_first():
    found = _dispositions(
        [_record("A", "Mayor Pro-Tem"), _record("A", "Council Member - Place 2")],
        [_record("A", "Council Member - Place 2"), _record("A", "Mayor Pro-Tem")],
    )
    assert [d.value for d in found["primary_role"]] == ["correct"]


def test_a_wrong_primary_role_is_still_caught():
    """The lenience is only about secondary roles — getting the published one wrong fails."""
    found = _dispositions(
        [_record("A", "Council Member - Place 2")],
        [_record("A", "Mayor")],
    )
    assert sorted(d.value for d in found["primary_role"]) == [
        "false_negative",
        "false_positive",
    ]


def test_division_and_seat_are_counted_apart():
    """Both come out of one label, and only the division half becomes a division_ocdid."""
    records = [_record("Beau Brudney", "Council Member Place 3 (East Ward)")]
    found = _dispositions(records, records)
    assert [d.value for d in found["district"]] == ["correct"]
    assert [d.value for d in found["designations_other"]] == ["correct"]


def test_different_wording_that_decomposes_the_same_is_correct():
    """What the old two-bag scorer punished: the model's phrasing, not its answer."""
    found = _dispositions(
        [_record("Rory Burke", "Council Member Position 4")],
        [_record("Rory Burke", "Councilman Pos. 4")],
    )
    assert [d.value for d in found["roles"]] == ["correct"]
    assert [d.value for d in found["designations_other"]] == ["correct"]


@pytest.mark.parametrize(
    "field, produced, fixture",
    [
        # Formats the pipeline collapses before storing, so the eval must too.
        ("phone", "(512) 978-2100", "512-978-2100"),
        ("phone", "512.978.2100", "(512) 978-2100"),
        ("email", "  Todd.Day@RanchoViejoTx.gov ", "todd.day@ranchoviejotx.gov"),
        ("url", "https://www.laportetx.gov/691/Mayor", "http://laportetx.gov/691/Mayor"),
        ("url", "https://laportetx.gov/691/Mayor/", "https://laportetx.gov/691/Mayor"),
    ],
)
def test_normalize_field_matches_what_the_app_stores(field, produced, fixture):
    from accuracy import normalize_field

    assert normalize_field(field, produced) == normalize_field(field, fixture)


def test_normalize_field_leaves_fields_the_app_does_not_normalize_alone():
    from accuracy import normalize_field

    assert normalize_field("start_date", "2025-05") == "2025-05"
    assert normalize_field("image", " local://a.png ") == "local://a.png"


def test_normalize_field_is_empty_for_absent_values():
    from accuracy import normalize_field

    assert normalize_field("phone", None) == ""
    assert normalize_field("url", "") == ""


def test_normalize_field_keeps_an_unparseable_phone_from_matching_a_real_one():
    from accuracy import normalize_field

    assert normalize_field("phone", "call city hall") != normalize_field(
        "phone", "(512) 978-2100"
    )


def test_a_contact_detail_on_one_record_answers_for_the_person():
    """Contact details belong to the person, so a second record's null must not erase it."""
    found = _dispositions(
        [
            _record("Sharlene T. Hetzel", "Mayor Pro-Tem"),
            _record("Sharlene T. Hetzel", "Council Member Place 2", phone="(325) 625-5114"),
        ],
        [_record("Sharlene T. Hetzel", "Mayor Pro-Tem", phone="325-625-5114")],
    )
    assert [d.value for d in found["phone"]] == ["correct"]
