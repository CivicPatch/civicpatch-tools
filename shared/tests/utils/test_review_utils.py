from unittest.mock import patch

import pytest

from shared.utils.review_utils import (
    _build_row,
    _check_division_sequence,
    _check_office_name_sequence,
    _check_people_count,
    _check_unique_roles,
    _collect_all_canonicals,
    _generate_issues,
    _inconsistent_count_issues,
    _missing_division_issues,
    _parse_division_entries,
    _parse_office_name_entries,
    generate_review,
    get_data_issues,
    has_data_issues,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _person(name="Test Person", division_ocdid=None, office_name=None):
    office = {}
    if division_ocdid is not None:
        office["division_ocdid"] = division_ocdid
    if office_name is not None:
        office["name"] = office_name
    return {"name": name, "office": office}


def _rp(name):
    return {"name": name}


DISTRICT_OCDID = "ocd-division/country:us/state:tx/place:austin/council_district:{}"


# ── _check_people_count ───────────────────────────────────────────────────────

def test_people_count_empty():
    assert _check_people_count([]) == ["Only 0 people found (minimum expected: 3)"]

def test_people_count_below_minimum():
    assert _check_people_count([_person()]) == ["Only 1 people found (minimum expected: 3)"]

def test_people_count_at_minimum():
    assert _check_people_count([_person()] * 3) == []

def test_people_count_above_minimum():
    assert _check_people_count([_person()] * 5) == []


# ── _parse_division_entries ───────────────────────────────────────────────────

def test_parse_division_entries_extracts_label_and_number():
    people = [_person(division_ocdid=DISTRICT_OCDID.format(2))]
    assert _parse_division_entries(people) == [("council district", 2)]

def test_parse_division_entries_skips_non_numeric():
    people = [_person(division_ocdid="ocd-division/country:us/state:tx")]
    assert _parse_division_entries(people) == []

def test_parse_division_entries_empty_ocdid():
    assert _parse_division_entries([_person()]) == []

def test_parse_division_entries_multiple():
    people = [
        _person(division_ocdid=DISTRICT_OCDID.format(1)),
        _person(division_ocdid=DISTRICT_OCDID.format(2)),
    ]
    assert _parse_division_entries(people) == [
        ("council district", 1),
        ("council district", 2),
    ]


# ── _missing_division_issues ──────────────────────────────────────────────────

def test_missing_division_issues_no_gap():
    assert _missing_division_issues("council district", [1, 2, 3]) == []

def test_missing_division_issues_single_gap():
    assert _missing_division_issues("council district", [1, 2, 4]) == [
        "Missing official with council district 3"
    ]

def test_missing_division_issues_multiple_gaps():
    issues = _missing_division_issues("council district", [1, 4])
    assert issues == [
        "Missing official with council district 2",
        "Missing official with council district 3",
    ]


# ── _inconsistent_count_issues ────────────────────────────────────────────────

def test_inconsistent_count_issues_all_same():
    assert _inconsistent_count_issues("council district", [1, 1, 2, 2, 3, 3]) == []

def test_inconsistent_count_issues_one_outlier():
    # districts 1 and 2 have 2 each, district 3 has only 1
    issues = _inconsistent_count_issues("council district", [1, 1, 2, 2, 3])
    assert issues == ["Council District 3 has 1 official(s) (expected 2)"]

def test_inconsistent_count_issues_all_unique():
    assert _inconsistent_count_issues("council district", [1, 2, 3]) == []


# ── _check_division_sequence ──────────────────────────────────────────────────

def test_division_sequence_contiguous():
    people = [_person(division_ocdid=DISTRICT_OCDID.format(n)) for n in [1, 2, 3]]
    assert _check_division_sequence(people) == []

def test_division_sequence_gap():
    people = [_person(division_ocdid=DISTRICT_OCDID.format(n)) for n in [1, 2, 4]]
    issues = _check_division_sequence(people)
    assert issues == ["Missing official with council district 3"]

def test_division_sequence_inconsistent_counts():
    people = [
        _person(division_ocdid=DISTRICT_OCDID.format(1)),
        _person(division_ocdid=DISTRICT_OCDID.format(1)),
        _person(division_ocdid=DISTRICT_OCDID.format(2)),
    ]
    issues = _check_division_sequence(people)
    assert issues == ["Council District 2 has 1 official(s) (expected 2)"]

def test_division_sequence_consistent_duplicates():
    people = [_person(division_ocdid=DISTRICT_OCDID.format(n)) for n in [1, 1, 2, 2, 3, 3]]
    assert _check_division_sequence(people) == []

def test_division_sequence_no_numeric_ocdids():
    people = [_person(division_ocdid="ocd-division/country:us/state:tx")] * 3
    assert _check_division_sequence(people) == []

def test_division_sequence_no_office():
    assert _check_division_sequence([{"name": "Test"}] * 3) == []


# ── _check_unique_roles ───────────────────────────────────────────────────────

def test_unique_roles_no_duplicates():
    people = [
        _person("Alice", office_name="Mayor"),
        _person("Bob", office_name="Council Member"),
    ]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=["Mayor"]):
        assert _check_unique_roles(people) == []

def test_unique_roles_duplicate_flagged():
    people = [
        _person("Alice", office_name="Mayor"),
        _person("Bob", office_name="Mayor"),
    ]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=["Mayor"]):
        issues = _check_unique_roles(people)
    assert len(issues) == 1
    assert "mayor" in issues[0]
    assert "Alice" in issues[0]
    assert "Bob" in issues[0]

def test_unique_roles_compound_office_name():
    people = [
        _person("Alice", office_name="Mayor - Council Member"),
        _person("Bob", office_name="Mayor - Finance Chair"),
    ]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=["Mayor"]):
        issues = _check_unique_roles(people)
    assert len(issues) == 1
    assert "mayor" in issues[0].lower()

def test_unique_roles_empty_unique_roles():
    people = [_person("Alice", office_name="Mayor"), _person("Bob", office_name="Mayor")]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=[]):
        assert _check_unique_roles(people) == []


# ── _parse_office_name_entries ────────────────────────────────────────────────

def test_parse_office_name_entries_extracts_label_and_number():
    people = [_person(office_name="Council Member - Place 1")]
    assert _parse_office_name_entries(people) == [("place", 1)]

def test_parse_office_name_entries_no_numeric_parts():
    people = [_person(office_name="Mayor"), _person(office_name="At-Large")]
    assert _parse_office_name_entries(people) == []

def test_parse_office_name_entries_skips_non_numeric_tokens():
    people = [_person(office_name="Council Member - Place 1")]
    entries = _parse_office_name_entries(people)
    assert ("council member", 1) not in entries

def test_parse_office_name_entries_multiple():
    people = [
        _person(office_name="Council Member - Place 1"),
        _person(office_name="Council Member - Place 2"),
        _person(office_name="Council Member - Place 3"),
    ]
    assert _parse_office_name_entries(people) == [("place", 1), ("place", 2), ("place", 3)]


# ── _check_office_name_sequence ───────────────────────────────────────────────

def test_office_name_sequence_contiguous():
    people = [_person(office_name=f"Council Member - Place {n}") for n in [1, 2, 3]]
    assert _check_office_name_sequence(people) == []

def test_office_name_sequence_gap():
    people = [_person(office_name=f"Council Member - Place {n}") for n in [1, 2, 4]]
    assert _check_office_name_sequence(people) == ["Missing official with place 3"]

def test_office_name_sequence_inconsistent_counts():
    people = [
        _person(office_name="Council Member - Place 1"),
        _person(office_name="Council Member - Place 1"),
        _person(office_name="Council Member - Place 2"),
    ]
    assert _check_office_name_sequence(people) == ["Place 2 has 1 official(s) (expected 2)"]

def test_office_name_sequence_no_numeric_parts():
    people = [_person(office_name="Mayor"), _person(office_name="At-Large"), _person(office_name="Treasurer")]
    assert _check_office_name_sequence(people) == []

def test_parse_office_name_entries_numeric_in_middle_token():
    # "Council Member - Seat 2 - Council" — numeric token is in the middle
    people = [_person(office_name="Council Member - Seat 2 - Council")]
    assert _parse_office_name_entries(people) == [("seat", 2)]

def test_office_name_sequence_numeric_in_middle_gap():
    people = [
        _person(office_name="Council Member - Seat 1 - Council"),
        _person(office_name="Council Member - Seat 2 - Council"),
        _person(office_name="Council Member - Seat 4 - Council"),
    ]
    assert _check_office_name_sequence(people) == ["Missing official with seat 3"]

def test_office_name_sequence_numeric_in_middle_contiguous():
    people = [_person(office_name=f"Council Member - Seat {n} - Council") for n in [1, 2, 3]]
    assert _check_office_name_sequence(people) == []


# ── _collect_all_canonicals ───────────────────────────────────────────────────

def test_collect_all_canonicals_union_and_sorted():
    assert _collect_all_canonicals({"Alice", "Bob"}, {"Bob", "Carol"}) == ["Alice", "Bob", "Carol"]

def test_collect_all_canonicals_empty():
    assert _collect_all_canonicals(set(), set()) == []


# ── _generate_issues ──────────────────────────────────────────────────────────

def test_generate_issues_clean():
    assert _generate_issues({"Alice", "Bob"}, {"Alice", "Bob"}) == []

def test_generate_issues_extra():
    assert _generate_issues({"Alice"}, {"Alice", "Bob"}) == ["Extra official: Bob"]

def test_generate_issues_missing():
    assert _generate_issues({"Alice", "Bob"}, {"Alice"}) == ["Missing official: Bob"]

def test_generate_issues_both():
    issues = _generate_issues({"Alice", "Carol"}, {"Alice", "Bob"})
    assert "Extra official: Bob" in issues
    assert "Missing official: Carol" in issues


# ── _build_row ────────────────────────────────────────────────────────────────

def test_build_row_in_both():
    assert _build_row("Alice", {"Alice"}, {"Alice"}) == {
        "name": "Alice", "in_research": True, "in_data": True
    }

def test_build_row_research_only():
    assert _build_row("Alice", {"Alice"}, set()) == {
        "name": "Alice", "in_research": True, "in_data": False
    }

def test_build_row_data_only():
    assert _build_row("Alice", set(), {"Alice"}) == {
        "name": "Alice", "in_research": False, "in_data": True
    }


# ── has_data_issues / get_data_issues ─────────────────────────────────────────

def test_has_data_issues_false_when_clean():
    people = [_person(division_ocdid=DISTRICT_OCDID.format(n)) for n in [1, 2, 3]]
    assert has_data_issues(people) is False

def test_has_data_issues_true_for_low_count():
    assert has_data_issues([_person()]) is True

def test_has_data_issues_true_for_gap():
    people = [_person(division_ocdid=DISTRICT_OCDID.format(n)) for n in [1, 3, 5]]
    assert has_data_issues(people) is True

def test_get_data_issues_empty_when_clean():
    people = [_person(division_ocdid=DISTRICT_OCDID.format(n)) for n in [1, 2, 3]]
    assert get_data_issues(people) == []

def test_get_data_issues_returns_count_issue():
    issues = get_data_issues([_person()])
    assert any("Only 1" in i for i in issues)


# ── generate_review ───────────────────────────────────────────────────────────

def test_generate_review_clean():
    research = [_rp(n) for n in ["Alice Smith", "Bob Jones", "Carol White"]]
    people = [_person(n) for n in ["Alice Smith", "Bob Jones", "Carol White"]]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=[]):
        result = generate_review(research, people)
    assert result["issues"] == []
    assert len(result["people_by_source"]) == 3

def test_generate_review_missing_official():
    research = [_rp(n) for n in ["Alice Smith", "Bob Jones", "Carol White"]]
    people = [_person(n) for n in ["Alice Smith", "Carol White", "Carol White"]]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=[]):
        result = generate_review(research, people)
    assert any("Missing official" in i for i in result["issues"])

def test_generate_review_too_few_people():
    research = [_rp("Alice Smith")]
    people = [_person("Alice Smith")]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=[]):
        result = generate_review(research, people)
    assert any("minimum expected" in i for i in result["issues"])

def test_generate_review_with_identities():
    research = [_rp(n) for n in ["Alice Smith", "Bob Jones", "Carol White"]]
    people = [_person(n) for n in ["Al Smith", "Bob Jones", "Carol White"]]
    with patch("shared.utils.review_utils.config_utils.get_unique_roles", return_value=[]):
        result = generate_review(research, people, identities={"Alice Smith": ["Al Smith"]})
    assert result["issues"] == []
