from shared.schemas import Issue, IssueCode
from shared.utils import name_utils
from shared.utils.review_utils import (
    ReviewInputs,
    _build_row,
    _check_division_numbering,
    _check_duplicate_unique_roles,
    _check_new_officials,
    _check_absent_officials,
    _check_too_few_people,
    _collect_all_canonicals,
    _parse_division_entries,
    build_review_summary,
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


# ── _collect_all_canonicals ───────────────────────────────────────────────────

def test_collect_all_canonicals_union_and_sorted():
    assert _collect_all_canonicals({"Alice", "Bob"}, {"Bob", "Carol"}) == ["Alice", "Bob", "Carol"]

def test_collect_all_canonicals_empty():
    assert _collect_all_canonicals(set(), set()) == []


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


# ── Structured issues: build_review_summary + the _check_* → Issue functions ──

def _official(name, person_id="", office_name=None, division_ocdid=None, labels=None):
    """A rendered roster row: `labels` verbatim, `office.name` the display join of them.

    Both, because that is what `_render` produces — the checks read `labels`, and keeping
    `office` here means a fixture cannot quietly stop resembling the real thing.
    """
    office = {}
    if office_name is not None:
        office["name"] = office_name
    if division_ocdid is not None:
        office["division_ocdid"] = division_ocdid
    if labels is None:
        labels = [office_name] if office_name else []
    return {"name": name, "id": person_id, "office": office, "labels": labels}


def test_check_absent_officials_is_list_level():
    issues = _check_absent_officials({"alice", "bob"}, {"alice"})
    assert len(issues) == 1
    assert issues[0].code == IssueCode.ABSENT_OFFICIAL
    assert "bob" in issues[0].message.lower()
    assert issues[0].person_ids == []
    assert issues[0].field is None


def test_check_new_officials_anchors_to_person_id():
    people = [_official("Carol White", person_id="c1")]
    canonical_map = name_utils.build_canonical_map(people, {})
    issues = _check_new_officials(people, canonical_map, research_canonicals=set())
    assert len(issues) == 1
    assert issues[0].code == IssueCode.NEW_OFFICIAL
    assert issues[0].person_ids == ["c1"]


def test_check_new_officials_new_person_degrades_to_list_level():
    people = [_official("New Person", person_id="")]  # not yet in the DB
    canonical_map = name_utils.build_canonical_map(people, {})
    issues = _check_new_officials(people, canonical_map, research_canonicals=set())
    assert issues[0].person_ids == []


def test_check_too_few_people():
    issues = _check_too_few_people([_official("A"), _official("B")])
    assert len(issues) == 1
    assert issues[0].code == IssueCode.TOO_FEW_PEOPLE
    assert issues[0].person_ids == []
    assert _check_too_few_people([_official(f"P{i}") for i in range(5)]) == []


def test_check_duplicate_unique_roles_anchors_to_holders():
    people = [
        _official("A", person_id="a1", office_name="Mayor"),
        _official("B", person_id="b1", office_name="Mayor"),
        _official("C", person_id="c1", office_name="Clerk"),
    ]
    issues = _check_duplicate_unique_roles(people, ["Mayor"])
    assert len(issues) == 1
    assert issues[0].code == IssueCode.DUPLICATE_UNIQUE_ROLE
    assert issues[0].field == "office.name"
    assert set(issues[0].person_ids) == {"a1", "b1"}


def test_check_division_numbering_gap_is_list_level():
    people = [
        _official("A", division_ocdid=DISTRICT_OCDID.format(1)),
        _official("B", division_ocdid=DISTRICT_OCDID.format(3)),  # gap at 2
    ]
    issues = _check_division_numbering(people)
    assert len(issues) == 1
    assert issues[0].code == IssueCode.DIVISION_NUMBERING_GAP
    assert "2" in issues[0].message
    assert issues[0].person_ids == []


def test_build_review_summary_returns_structured_issues():
    research = [_rp("Alice Smith"), _rp("Bob Jones")]
    people = [_official("Alice Smith", person_id="a1", office_name="Mayor")]  # Bob missing, too few
    result = build_review_summary(research, people)
    assert result["origin_source"] == "google_gemini"
    assert "people_by_source" in result
    issues = result["issues"]
    assert issues and all(isinstance(i, Issue) for i in issues)
    codes = {i.code for i in issues}
    assert IssueCode.ABSENT_OFFICIAL in codes  # Bob Jones
    assert IssueCode.TOO_FEW_PEOPLE in codes    # 1 < 3


def test_build_review_summary_normalizes_official_objects():
    from shared.schemas import Office, Official

    official = Official(
        name="Jane",
        office=Office(name="Mayor"),
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:co/place:denver/government",
        source_urls=["https://denvergov.org/council"],
        updated_at="2025-06-27T19:43:55+00:00",
        id="j1",
    )
    # Passing Official objects (not dicts) must not raise — they normalize via model_dump.
    result = build_review_summary([], [official])
    assert all(isinstance(i, Issue) for i in result["issues"])


def test_build_review_summary_matches_aliases():
    # An explicit identity alias must not read as a missing/extra official.
    research = [_rp("Michelle Drass"), _rp("Bob Jones"), _rp("Carol White")]
    people = [_official("Michelle D Rass"), _official("Bob Jones"), _official("Carol White")]
    inputs = ReviewInputs(identities={"Michelle Drass": ["Michelle D Rass"]})
    codes = {i.code for i in build_review_summary(research, people, inputs)["issues"]}
    assert IssueCode.ABSENT_OFFICIAL not in codes
    assert IssueCode.NEW_OFFICIAL not in codes
