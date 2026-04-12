import pytest
from shared.utils.review_utils import (
    ReviewInputs,
    _check_division_sequence,
    _check_people_count,
    _collect_all_canonicals,
    _generate_issues,
    _build_row,
    generate_review,
    get_data_issues,
    has_data_issues,
)


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
    assert issues == ["Missing official with council district 3"]

def test_division_sequence_duplicate():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:2"),
    ]
    issues = _check_division_sequence(people)
    assert issues == ["Council District 2 has 1 official(s) (expected 2)"]

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


# ── get_data_issues ───────────────────────────────────────────────────────────

def test_get_data_issues_empty_when_clean():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:2"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:3"),
    ]
    assert get_data_issues(people) == []

def test_get_data_issues_returns_count_issue():
    issues = get_data_issues([_person()])
    assert len(issues) == 1
    assert "Only 1" in issues[0]

def test_get_data_issues_returns_sequence_issue():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:3"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:5"),
    ]
    issues = get_data_issues(people)
    assert any("Missing official" in i for i in issues)

def test_get_data_issues_combines_both():
    people = [
        _person("ocd-division/country:us/state:tx/place:austin/council_district:1"),
        _person("ocd-division/country:us/state:tx/place:austin/council_district:3"),
    ]
    issues = get_data_issues(people)
    assert any("Only 2" in i for i in issues)
    assert any("Missing official" in i for i in issues)


# ── _collect_all_canonicals ───────────────────────────────────────────────────

def test_collect_all_canonicals_union_and_sorted():
    result = _collect_all_canonicals({"Alice", "Bob"}, {"Bob", "Carol"})
    assert result == ["Alice", "Bob", "Carol"]

def test_collect_all_canonicals_disjoint():
    result = _collect_all_canonicals({"Zoe"}, {"Amy"})
    assert result == ["Amy", "Zoe"]

def test_collect_all_canonicals_empty():
    assert _collect_all_canonicals(set(), set()) == []


# ── _generate_issues ─────────────────────────────────────────────────────────

def test_generate_issues_no_issues_when_equal():
    assert _generate_issues({"Alice", "Bob"}, {"Alice", "Bob"}) == []

def test_generate_issues_extra_official():
    issues = _generate_issues({"Alice"}, {"Alice", "Bob"})
    assert issues == ["Extra official: Bob"]

def test_generate_issues_missing_official():
    issues = _generate_issues({"Alice", "Bob"}, {"Alice"})
    assert issues == ["Missing official: Bob"]

def test_generate_issues_both():
    issues = _generate_issues({"Alice", "Carol"}, {"Alice", "Bob"})
    assert "Extra official: Bob" in issues
    assert "Missing official: Carol" in issues


# ── _build_row ────────────────────────────────────────────────────────────────

def test_build_row_in_both():
    row = _build_row("Alice", {"Alice"}, {"Alice"})
    assert row == {"name": "Alice", "in_research": True, "in_data": True}

def test_build_row_research_only():
    row = _build_row("Alice", {"Alice"}, set())
    assert row == {"name": "Alice", "in_research": True, "in_data": False}

def test_build_row_data_only():
    row = _build_row("Alice", set(), {"Alice"})
    assert row == {"name": "Alice", "in_research": False, "in_data": True}


# ── generate_review ───────────────────────────────────────────────────────────

def _rp(name):
    return {"name": name}

def _dp(name, division_ocdid=None):
    office = {"division_ocdid": division_ocdid} if division_ocdid else {}
    return {"name": name, "office": office}

def test_generate_review_clean_match():
    research = [_rp("Alice Smith"), _rp("Bob Jones"), _rp("Carol White")]
    people = [_dp("Alice Smith"), _dp("Bob Jones"), _dp("Carol White")]
    result = generate_review(research, people)
    assert result["issues"] == []
    assert len(result["people_by_source"]) == 3

def test_generate_review_missing_official():
    research = [_rp("Alice Smith"), _rp("Bob Jones"), _rp("Carol White")]
    people = [_dp("Alice Smith"), _dp("Carol White"), _dp("Carol White")]
    result = generate_review(research, people)
    assert any("Missing official" in i for i in result["issues"])

def test_generate_review_extra_official():
    research = [_rp("Alice Smith"), _rp("Carol White"), _rp("Carol White")]
    people = [_rp("Alice Smith"), _rp("Bob Jones"), _rp("Carol White")]
    result = generate_review(research, people)
    assert any("Extra official" in i for i in result["issues"])

def test_generate_review_too_few_people():
    research = [_rp("Alice Smith")]
    people = [_dp("Alice Smith")]
    result = generate_review(research, people)
    assert any("minimum expected" in i for i in result["issues"])

def test_generate_review_rows_contain_all_names():
    research = [_rp("Alice Smith"), _rp("Bob Jones"), _rp("Carol White")]
    people = [_dp("Alice Smith"), _dp("Bob Jones"), _dp("Carol White")]
    result = generate_review(research, people)
    names = {r["name"] for r in result["people_by_source"]}
    assert "Alice Smith" in names
    assert "Bob Jones" in names
    assert "Carol White" in names

def test_generate_review_with_identities():
    # "Al Smith" is an alias for "Alice Smith"
    research = [_rp("Alice Smith"), _rp("Bob Jones"), _rp("Carol White")]
    people = [_dp("Al Smith"), _dp("Bob Jones"), _dp("Carol White")]
    inputs = ReviewInputs(identities={"Alice Smith": ["Al Smith"]})
    result = generate_review(research, people, inputs)
    assert result["issues"] == []


def test_generate_review_excludes_unrecognized_roles():
    research = [_rp(n) for n in ["Alice", "Bob", "Carol"]]
    people = [_dp(n) for n in ["Alice", "Bob", "Carol"]]
    inputs = ReviewInputs(unrecognized_roles=[{"role": "Alderman", "person_name": "Alice"}])
    result = generate_review(research, people, inputs)
    assert not any("Alderman" in i for i in result["issues"])
