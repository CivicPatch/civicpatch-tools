import pytest

from core.entry_rows import (
    ImportRow,
    RowError,
    Sighting,
    already_handled,
    parse_rows,
    roster_columns,
    rows_by_jurisdiction,
)

_SHERBORN = (
    "ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government"
)
_CONCORD = _SHERBORN.replace("sherborn", "concord")
_SHEET = "https://docs.google.com/spreadsheets/d/abc/export?format=csv&gid=0"


def _row(**overrides) -> dict:
    row = {
        "jurisdiction_ocdid": _SHERBORN,
        "name": "Ana Reyes",
        "label": "Select Board Member",
        "url": "",
        "phone": "",
        "email": "",
        "image": "",
        "start_date": "",
        "end_date": "",
    }
    row.update(overrides)
    return row


def _flags(errors) -> set:
    return {(error.line, error.column) for error in errors}


# --- the happy path ---


@pytest.mark.unit
def test_a_row_becomes_a_sighting():
    rows, errors = parse_rows([_row()], _SHEET)
    assert errors == []
    assert rows[0].sighting.name == "Ana Reyes"
    assert rows[0].sighting.label == "Select Board Member"
    assert rows[0].jurisdiction_ocdid == _SHERBORN


@pytest.mark.unit
def test_the_sheet_is_the_source_url():
    """A curated record's source is the sheet a human authored. Sheets gives a row no durable
    url of its own, so there is nothing finer to point at."""
    rows, _ = parse_rows([_row()], _SHEET)
    assert rows[0].sighting.source_url == _SHEET


@pytest.mark.unit
def test_line_numbers_count_the_header():
    """They have to match the row gutter a volunteer is looking at."""
    rows, _ = parse_rows([_row(), _row(name="Bo Chen")], _SHEET)
    assert [row.line for row in rows] == [2, 3]


@pytest.mark.unit
def test_blanks_become_none_and_whitespace_is_stripped():
    rows, _ = parse_rows(
        [_row(name="  Ana Reyes  ", phone="  ", email="a@b.gov")], _SHEET
    )
    assert rows[0].sighting.name == "Ana Reyes"
    assert rows[0].sighting.phone is None
    assert rows[0].sighting.email == "a@b.gov"


@pytest.mark.unit
def test_the_sheet_carries_no_ids():
    """Matching is ingest's job. A uuid in a cell would let a curator mis-seat somebody with a
    value nothing can validate, so the model has nowhere to put one."""
    rows, _ = parse_rows([_row(person_id="anything", post_id="anything")], _SHEET)
    assert not hasattr(rows[0], "person_id")
    assert not hasattr(rows[0].sighting, "post_id")


# --- what blocks a row ---


@pytest.mark.unit
@pytest.mark.parametrize("column", ["jurisdiction_ocdid", "name", "label"])
def test_the_three_required_columns(column):
    _, errors = parse_rows([_row(**{column: ""})], _SHEET)
    assert _flags(errors) == {(2, column)}


@pytest.mark.unit
@pytest.mark.parametrize("value", ["2026", "2026-01", "2026-01-15"])
def test_partial_dates_are_allowed(value):
    """`source_records.start_date` is text for exactly this reason — sources give partial dates."""
    _, errors = parse_rows([_row(start_date=value)], _SHEET)
    assert errors == []


@pytest.mark.unit
@pytest.mark.parametrize("value", ["15/01/2026", "Jan 2026", "2026-1-5"])
def test_a_date_the_column_cannot_hold_is_an_error(value):
    _, errors = parse_rows([_row(end_date=value)], _SHEET)
    assert _flags(errors) == {(2, "end_date")}


@pytest.mark.unit
@pytest.mark.parametrize(
    "column,value",
    [
        ("phone", "not-a-number"),
        ("email", "missing-the-at-sign"),
        ("url", "example.gov"),
        ("url", "http://localhost"),
    ],
)
def test_contact_columns_are_checked_here_not_further_down(column, value):
    """The same rules `SubmittedPersonRecord` applies, run at the row so a volunteer sees the bad
    cell in their sheet. Before this the three passed through unchecked."""
    _, errors = parse_rows([_row(**{column: value})], _SHEET)
    assert _flags(errors) == {(2, column)}


@pytest.mark.unit
@pytest.mark.parametrize(
    "column,value",
    [
        ("phone", "206-684-4000"),
        ("email", "clerk@example.gov"),
        ("url", "https://example.gov/council"),
    ],
)
def test_a_contact_column_that_is_fine_is_left_alone(column, value):
    _, errors = parse_rows([_row(**{column: value})], _SHEET)
    assert errors == []


@pytest.mark.unit
def test_an_empty_contact_column_is_not_an_error():
    """All three are optional — absent is not the same as wrong."""
    _, errors = parse_rows([_row(phone="", email="", url="")], _SHEET)
    assert errors == []


@pytest.mark.unit
def test_one_bad_row_does_not_cost_the_others_their_turn():
    rows, errors = parse_rows([_row(), _row(name=""), _row(name="Bo Chen")], _SHEET)
    assert [row.line for row in rows] == [2, 4]
    assert _flags(errors) == {(3, "name")}


# --- one person, one seat ---


@pytest.mark.unit
def test_the_same_person_twice_in_one_jurisdiction_is_an_error():
    """`memberships` has a unique index on (person_id, organization_id) among open rows and a
    jurisdiction has one organization, so two rows for one person is unrepresentable."""
    _, errors = parse_rows([_row(), _row(label="Chair")], _SHEET)
    assert _flags(errors) == {(3, "name")}
    assert "line 2" in errors[0].message


@pytest.mark.unit
def test_duplicate_detection_ignores_case():
    _, errors = parse_rows([_row(name="Ana Reyes"), _row(name="ana reyes")], _SHEET)
    assert _flags(errors) == {(3, "name")}


@pytest.mark.unit
def test_the_same_name_in_two_jurisdictions_is_ordinary():
    _, errors = parse_rows([_row(), _row(jurisdiction_ocdid=_CONCORD)], _SHEET)
    assert errors == []


# --- grouping ---


@pytest.mark.unit
def test_rows_group_by_jurisdiction():
    rows, _ = parse_rows(
        [_row(), _row(name="Bo Chen"), _row(jurisdiction_ocdid=_CONCORD)], _SHEET
    )
    grouped = rows_by_jurisdiction(rows)
    assert sorted(grouped) == sorted([_SHERBORN, _CONCORD])
    assert len(grouped[_SHERBORN]) == 2


# ── Columns out ──────────────────────────────────────────────────────────────

_STAMP = "2026-08-27 14:02"


def _parsed_row(line: int, ocdid: str = _SHERBORN, name: str = "Ana Reyes") -> ImportRow:
    return ImportRow(
        line=line,
        jurisdiction_ocdid=ocdid,
        sighting=Sighting(name=name, label="Chair", source_url="s"),
    )


def _row_error(line: int, ocdid: str = _SHERBORN, column: str | None = "label") -> RowError:
    return RowError(
        line=line, jurisdiction_ocdid=ocdid, column=column, message="required"
    )


# --- roster tab ---


@pytest.mark.unit
def test_an_imported_row_says_so_and_carries_no_error():
    columns = roster_columns([_parsed_row(2)], [], 1, {_SHERBORN}, _STAMP)
    assert columns["status"] == ["imported"]
    assert columns["error"] == [""]


@pytest.mark.unit
def test_a_rejected_row_names_its_column():
    columns = roster_columns([], [_row_error(2)], 1, set(), _STAMP)
    assert columns["status"] == ["error"]
    assert columns["error"] == ["label: required"]


@pytest.mark.unit
def test_a_good_row_in_a_blocked_town_points_elsewhere():
    """Most of a blocked town is rows that are perfectly fine. Saying 'error' against them would
    have the volunteer hunting for a fault that is on somebody else's line."""
    columns = roster_columns([_parsed_row(2)], [_row_error(3)], 2, set(), _STAMP)
    assert columns["status"] == ["blocked", "error"]
    assert columns["error"][0] == "another row in this town was rejected"


@pytest.mark.unit
def test_every_row_gets_a_value_so_stale_errors_clear():
    """A row that failed last run and is fine now must not keep last run's message — the
    volunteer would chase a problem they already fixed."""
    columns = roster_columns([_parsed_row(2), _parsed_row(3, name="Bo Chen")], [], 2, {_SHERBORN}, _STAMP)
    assert columns["error"] == ["", ""]
    assert len(columns["status"]) == 2
    assert columns["last_import_at"] == [_STAMP, _STAMP]
# --- jurisdictions tab ---
# --- what Sheets does to a date ---


@pytest.mark.unit
def test_a_date_arrives_as_a_sheets_serial():
    """The import reads UNFORMATTED_VALUE so a phone number survives as typed, which means a
    real date comes back as days since 1899-12-30 rather than the text somebody entered."""
    rows, errors = parse_rows([_row(start_date="45292", end_date="45658")], _SHEET)
    assert errors == []
    assert rows[0].sighting.start_date == "2024-01-01"
    assert rows[0].sighting.end_date == "2025-01-01"


@pytest.mark.unit
def test_a_bare_year_is_left_alone():
    """A year is an integer too. 2024 must stay 2024, not become 1905-07-16."""
    rows, errors = parse_rows([_row(start_date="2024")], _SHEET)
    assert errors == []
    assert rows[0].sighting.start_date == "2024"


@pytest.mark.unit
def test_a_partial_date_survives():
    rows, errors = parse_rows([_row(start_date="2022-01")], _SHEET)
    assert errors == []
    assert rows[0].sighting.start_date == "2022-01"


@pytest.mark.unit
def test_text_that_is_not_a_date_still_fails():
    """Converting serials must not turn the check into a rubber stamp."""
    _, errors = parse_rows([_row(start_date="Jan 2026")], _SHEET)
    assert [(e.column, "not YYYY" in e.message) for e in errors] == [
        ("start_date", True)
    ]


# --- the status column decides whether a locality is re-imported ---


def _parsed(*rows: dict):
    parsed, errors = parse_rows(list(rows), _SHEET)
    assert errors == []
    return parsed


@pytest.mark.unit
def test_a_locality_whose_rows_all_say_imported_is_done():
    assert already_handled(_parsed(_row(status="imported"), _row(name="Bo", status="imported")))


@pytest.mark.unit
def test_a_blank_status_brings_the_locality_back():
    """What a volunteer does after fixing a row: clear the cell, press Import."""
    assert not already_handled(_parsed(_row(status="imported"), _row(name="Bo", status="")))


@pytest.mark.unit
def test_any_status_counts_as_handled_not_just_imported():
    """The column is the app's account of what it did. `error` and `blocked` have been answered
    for too — the volunteer clears the cell to ask again."""
    assert already_handled(_parsed(_row(status="error")))
    assert already_handled(_parsed(_row(status="blocked")))


@pytest.mark.unit
def test_a_row_this_run_did_not_touch_keeps_its_status():
    """The loop this closes: the write-back blanked every row it had not just imported, so the
    next run saw a blank, re-imported, and the run after skipped again — unchanged, imported,
    unchanged, on a sheet nobody edited."""
    rows = _parsed(_row(status="imported"))
    columns = roster_columns(rows, [], len(rows), set(), _STAMP)

    assert columns["status"] == ["imported"]


@pytest.mark.unit
def test_a_never_imported_locality_has_no_status_at_all():
    assert not already_handled(_parsed(_row()))


@pytest.mark.unit
def test_one_row_wanting_attention_brings_the_whole_roster():
    """All, not any. A card carrying only the cleared row would propose closing everybody
    else's membership when published."""
    rows = _parsed(_row(status="imported"), _row(name="Bo", status=""))
    assert not already_handled(rows)
    assert len(rows) == 2


@pytest.mark.unit
def test_blank_rows_are_grid_not_errors():
    """Sheets returns every line in the used range. A tab with four entries and 140 spare lines
    was reporting 420 `required` errors and blocking both jurisdictions on rows nobody typed."""
    blank = {column: "" for column in _row()}
    parsed, errors = parse_rows([_row(), blank, blank, blank], _SHEET)

    assert len(parsed) == 1
    assert errors == []


@pytest.mark.unit
def test_a_half_filled_row_is_still_an_error():
    """The distinction that matters: somebody picked a jurisdiction and stopped. That is a row
    they meant to write, and telling them about it is the point."""
    started = {column: "" for column in _row()}
    started["jurisdiction_ocdid"] = _SHERBORN

    _, errors = parse_rows([started], _SHEET)

    assert {column for _, column in _flags(errors)} == {"name", "label"}


@pytest.mark.unit
def test_line_numbers_survive_skipped_blanks():
    """Blank rows still occupy a line, so a row after one must keep the gutter number the
    volunteer sees."""
    blank = {column: "" for column in _row()}
    parsed, _ = parse_rows([blank, blank, _row()], _SHEET)

    assert [row.line for row in parsed] == [4]


@pytest.mark.unit
def test_a_stamped_but_untyped_row_is_still_blank():
    """The bug this actually was. The write-back stamped `last_import_at` down the used range,
    so every spare line carried a timestamp — and a blankness check over all values then read
    143 empty lines as occupied and rejected each three times."""
    stamped = {column: "" for column in _row()}
    stamped["last_import_at"] = "2026-09-03 22:41"

    parsed, errors = parse_rows([_row(), stamped], _SHEET)

    assert len(parsed) == 1
    assert errors == []


@pytest.mark.unit
def test_spare_lines_are_not_stamped():
    """The other half: stop creating the condition. A line the parse produced nothing for gets
    no timestamp, so it stays a line nobody wrote."""
    columns = roster_columns([], [], 3, set(), _STAMP)

    assert columns["last_import_at"] == ["", "", ""]


@pytest.mark.unit
def test_rows_the_run_saw_are_still_stamped():
    parsed, errors = parse_rows([_row()], _SHEET)
    columns = roster_columns(parsed, errors, 1, {_SHERBORN}, _STAMP)

    assert columns["last_import_at"] == [_STAMP]
