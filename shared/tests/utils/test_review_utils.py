import pytest
from shared.utils.review_utils import _check_division_sequence, _check_people_count, has_data_issues


def _person(division_ocdid=None):
    office = {"division_ocdid": division_ocdid} if division_ocdid is not None else {}
    return {"name": "Test Person", "office": office}


# ── _check_people_count ───────────────────────────────────────────────────────

def test_people_count_below_minimum():
    assert _check_people_count([_person()]) == [
        "Only 1 people found (minimum expected: 3)"
    ]

def test_people_count_at_minimum():
    assert _check_people_count([_person(), _person(), _person()]) == []

def test_people_count_above_minimum():
    assert _check_people_count([_person()] * 5) == []

def test_people_count_empty():
    assert _check_people_count([]) == ["Only 0 people found (minimum expected: 3)"]


# ── _check_division_sequence ──────────────────────────────────────────────────

def test_division_sequence_contiguous():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:2"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:3"),
    ]
    assert _check_division_sequence(people) == []

def test_division_sequence_gap():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:2"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:4"),
    ]
    issues = _check_division_sequence(people)
    assert len(issues) == 1
    assert "irregular" in issues[0]
    assert "[1, 2, 4]" in issues[0]
    assert "[1, 2, 3, 4]" in issues[0]

def test_division_sequence_duplicate():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:2"),
    ]
    issues = _check_division_sequence(people)
    assert len(issues) == 1
    assert "irregular" in issues[0]

def test_division_sequence_no_numeric_ocdids():
    people = [
        _person("ocd-division/country:us/state:tx"),
        _person("ocd-division/country:us/state:tx"),
    ]
    assert _check_division_sequence(people) == []

def test_division_sequence_missing_office():
    people = [{"name": "Test"}, {"name": "Other"}]
    assert _check_division_sequence(people) == []

def test_division_sequence_single_district():
    people = [_person("ocd-division/country:us/state:tx/place:austin/council_district:1")]
    assert _check_division_sequence(people) == []


# ── has_data_issues ───────────────────────────────────────────────────────────

def test_has_data_issues_false_when_clean():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:2"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:3"),
    ]
    assert has_data_issues(people) is False

def test_has_data_issues_true_for_low_count():
    assert has_data_issues([_person()]) is True

def test_has_data_issues_true_for_gap():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:3"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:5"),
    ]
    assert has_data_issues(people) is True
