"""Unit tests for the Sheets read/write helpers.

Nothing here reaches Google — the service is a mock, and what is asserted is the A1 notation we
hand it. That is where the risk actually is: a malformed range is rejected wholesale, and the
first time anyone would notice is the first real import.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.sheets import (
    _column_letter,
    clear_rows_from,
    ensure_tab,
    quote_tab,
    write_columns,
    write_rows,
)

SPREADSHEET = "sheet-abc"
TAB = "Entry · Roster"
HEADER = ["jurisdiction_ocdid", "name", "label", "status", "error"]


def _service(header: list[str], updated: int = 0) -> MagicMock:
    service = MagicMock()
    values = service.spreadsheets.return_value.values.return_value
    values.get.return_value.execute.return_value = {"values": [header]}
    values.batchUpdate.return_value.execute.return_value = {
        "totalUpdatedCells": updated
    }
    return service


def _body(service: MagicMock) -> dict:
    values = service.spreadsheets.return_value.values.return_value
    return values.batchUpdate.call_args.kwargs["body"]


@pytest.mark.unit
def test_a_tab_name_with_spaces_is_quoted():
    """Every entry tab is named like this, and A1 notation rejects it unquoted."""
    assert quote_tab(TAB) == "'Entry · Roster'"


@pytest.mark.unit
def test_an_apostrophe_in_a_tab_name_is_doubled():
    """Single quotes are the delimiter, so an internal one has to escape itself."""
    assert quote_tab("Martha's Vineyard") == "'Martha''s Vineyard'"


@pytest.mark.unit
@pytest.mark.parametrize(
    "index,letter",
    [(0, "A"), (25, "Z"), (26, "AA"), (27, "AB"), (51, "AZ"), (52, "BA")],
)
def test_column_letters_carry_correctly(index: int, letter: str):
    """Spreadsheet columns are bijective base-26, not base-26 — the wrap at Z is the trap."""
    assert _column_letter(index) == letter


@pytest.mark.unit
def test_a_column_is_written_by_header_position_below_the_header():
    """`status` is the fourth column, so it is D — and the write starts at row 2, leaving the
    header alone."""
    service = _service(HEADER, updated=3)
    with patch("lib.sheets.get_service", return_value=service):
        written = write_columns(
            SPREADSHEET, TAB, {"status": ["imported", "imported", "error"]}
        )

    assert written == 3
    [entry] = _body(service)["data"]
    assert entry["range"] == "'Entry · Roster'!D2:D4"
    assert entry["values"] == [["imported"], ["imported"], ["error"]]


@pytest.mark.unit
def test_values_are_written_raw():
    """USER_ENTERED would turn a phone number into an integer and `03/04` into a date."""
    service = _service(HEADER, updated=1)
    with patch("lib.sheets.get_service", return_value=service):
        write_columns(SPREADSHEET, TAB, {"error": ["name: required"]})

    assert _body(service)["valueInputOption"] == "RAW"


@pytest.mark.unit
def test_an_empty_column_is_skipped_rather_than_written_backwards():
    """A header-only tab yields no values, and `D2:D1` is a range the API refuses."""
    service = _service(HEADER)
    with patch("lib.sheets.get_service", return_value=service):
        written = write_columns(SPREADSHEET, TAB, {"status": []})

    assert written == 0
    service.spreadsheets.return_value.values.return_value.batchUpdate.assert_not_called()


@pytest.mark.unit
def test_a_column_the_sheet_does_not_have_is_refused():
    """Better than writing into whatever happens to sit at that index."""
    service = _service(HEADER)
    with patch("lib.sheets.get_service", return_value=service):
        with pytest.raises(ValueError, match="last_import_at"):
            write_columns(SPREADSHEET, TAB, {"last_import_at": ["14:02"]})


@pytest.mark.unit
def test_the_header_is_matched_case_insensitively():
    """A volunteer titling the column `Status` is not a reason to fail the write-back."""
    service = _service(["jurisdiction_ocdid", "Name", "Status"], updated=1)
    with patch("lib.sheets.get_service", return_value=service):
        write_columns(SPREADSHEET, TAB, {"status": ["imported"]})

    [entry] = _body(service)["data"]
    assert entry["range"] == "'Entry · Roster'!C2:C2"


# --- the roster tabs: created, sized, protected, written, trimmed ---

STATE_TAB = "Live[People][TX]"
# An arbitrary tab width for these tests; index 21 is column V.
COLUMNS = 22
WIDTHS = [120] * COLUMNS
# Texas, plus its header row. The number that breaks a default 1000-row grid.
TEXAS_ROWS = 5845


def _grid_service(existing: dict | None = None, new_sheet_id: int = 77) -> MagicMock:
    service = MagicMock()
    spreadsheets = service.spreadsheets.return_value
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [existing] if existing else []
    }
    spreadsheets.batchUpdate.return_value.execute.return_value = {
        "replies": [
            {"addSheet": {"properties": {"sheetId": new_sheet_id, "title": STATE_TAB}}}
        ]
    }
    spreadsheets.values.return_value.update.return_value.execute.return_value = {
        "updatedCells": 0
    }
    return service


def _existing_tab(rows: int = 1000, columns: int = 26, protections=()) -> dict:
    return {
        "properties": {
            "sheetId": 42,
            "title": STATE_TAB,
            "gridProperties": {"rowCount": rows, "columnCount": columns},
        },
        "protectedRanges": [{"description": name} for name in protections],
    }


def _requests(service: MagicMock) -> list:
    """Every request across every batchUpdate call, flattened."""
    return [
        request
        for call in service.spreadsheets.return_value.batchUpdate.call_args_list
        for request in call.kwargs["body"]["requests"]
    ]


def _of_kind(service: MagicMock, kind: str) -> list:
    return [request[kind] for request in _requests(service) if kind in request]


def _resizes(service: MagicMock) -> list:
    """Only the grid-resizing updates. Freezing the header row is an `updateSheetProperties`
    too, so matching on the request kind alone would count it as a resize."""
    return [
        request
        for request in _of_kind(service, "updateSheetProperties")
        if "rowCount" in request["fields"]
    ]


@pytest.mark.unit
def test_ensure_tab_reports_the_grid_it_left_behind():
    """The caller trims from the first unused row, and a range past the grid is an error rather
    than a no-op — so it has to know where the grid ends."""
    service = _grid_service(_existing_tab(rows=8000, columns=COLUMNS))
    with patch("lib.sheets.get_service", return_value=service):
        assert ensure_tab(SPREADSHEET, STATE_TAB, TEXAS_ROWS, WIDTHS) == 8000


@pytest.mark.unit
def test_ensure_tab_reports_the_grown_size_when_it_grew():
    service = _grid_service(_existing_tab(rows=1000, columns=COLUMNS))
    with patch("lib.sheets.get_service", return_value=service):
        assert ensure_tab(SPREADSHEET, STATE_TAB, TEXAS_ROWS, WIDTHS) == TEXAS_ROWS


@pytest.mark.unit
def test_a_missing_tab_is_created_sized_to_its_rows():
    """A new state's tab is the backend's to make — nothing else knows the state exists."""
    service = _grid_service()
    with patch("lib.sheets.get_service", return_value=service):
        ensure_tab(SPREADSHEET, STATE_TAB, TEXAS_ROWS, WIDTHS)

    [added] = _of_kind(service, "addSheet")
    assert added["properties"]["title"] == STATE_TAB
    assert added["properties"]["gridProperties"] == {
        "rowCount": TEXAS_ROWS,
        "columnCount": COLUMNS,
    }


@pytest.mark.unit
def test_a_tab_too_small_for_texas_is_grown_before_the_write():
    """The one that fails in production and nowhere else: `values.update` refuses a range past
    the grid rather than growing it, and a default tab is 1000 rows against Texas's 5,844."""
    service = _grid_service(_existing_tab(rows=1000))
    with patch("lib.sheets.get_service", return_value=service):
        ensure_tab(SPREADSHEET, STATE_TAB, TEXAS_ROWS, WIDTHS)

    [resized] = _resizes(service)
    assert resized["properties"]["gridProperties"]["rowCount"] == TEXAS_ROWS


@pytest.mark.unit
def test_a_tab_already_big_enough_is_left_alone():
    service = _grid_service(_existing_tab(rows=8000, columns=COLUMNS))
    with patch("lib.sheets.get_service", return_value=service):
        ensure_tab(SPREADSHEET, STATE_TAB, TEXAS_ROWS, WIDTHS)

    assert _resizes(service) == []


@pytest.mark.unit
def test_the_grid_is_never_shrunk():
    """Shrinking would delete cells mid-sync. The trim after the write is what removes stale
    rows, and it clears values rather than resizing the grid."""
    service = _grid_service(_existing_tab(rows=8000, columns=30))
    with patch("lib.sheets.get_service", return_value=service):
        ensure_tab(SPREADSHEET, STATE_TAB, 100, WIDTHS)

    assert _resizes(service) == []


@pytest.mark.unit
def test_a_new_tab_is_protected_and_formatted_as_text():
    """Both were the Apps Script's job for tabs it created. Without them an app-owned tab is
    silently editable, and a volunteer's edit vanishes on the next sync."""
    service = _grid_service()
    with patch("lib.sheets.get_service", return_value=service):
        ensure_tab(SPREADSHEET, STATE_TAB, TEXAS_ROWS, WIDTHS)

    [protected] = _of_kind(service, "addProtectedRange")
    assert protected["protectedRange"]["warningOnly"] is True
    assert _of_kind(service, "repeatCell")


@pytest.mark.unit
def test_a_rerun_does_not_stack_a_second_protection():
    """`ensure_tab` runs before every write, so an unconditional add would pile up one
    protected range per sync."""
    service = _grid_service(
        _existing_tab(rows=8000, columns=COLUMNS, protections=[STATE_TAB + " (app-owned)"])
    )
    with patch("lib.sheets.get_service", return_value=service):
        ensure_tab(SPREADSHEET, STATE_TAB, TEXAS_ROWS, WIDTHS)

    assert _of_kind(service, "addProtectedRange") == []


@pytest.mark.unit
def test_rows_are_written_at_the_offset_they_are_given():
    """Chunked writes address themselves, so the second chunk must land below the first."""
    service = _grid_service()
    with patch("lib.sheets.get_service", return_value=service):
        write_rows(SPREADSHEET, STATE_TAB, [["a"] * COLUMNS, ["b"] * COLUMNS], 2002)

    call = service.spreadsheets.return_value.values.return_value.update.call_args
    assert call.kwargs["range"] == f"'{STATE_TAB}'!A2002:V2003"
    assert call.kwargs["valueInputOption"] == "RAW"


@pytest.mark.unit
def test_writing_no_rows_touches_the_sheet_at_all():
    """A state we hold nothing for — Maine and Delaware today. `A2:V1` is a range the API
    refuses outright."""
    service = _grid_service()
    with patch("lib.sheets.get_service", return_value=service):
        assert write_rows(SPREADSHEET, STATE_TAB, [], 2) == 0

    service.spreadsheets.return_value.values.return_value.update.assert_not_called()


@pytest.mark.unit
def test_the_trim_clears_from_the_first_unused_row_down():
    """Write-then-trim: a state that lost rows must not keep the tail of the last sync."""
    service = _grid_service()
    with patch("lib.sheets.get_service", return_value=service):
        clear_rows_from(SPREADSHEET, STATE_TAB, 500, COLUMNS)

    call = service.spreadsheets.return_value.values.return_value.clear.call_args
    # Bounded to the tab's real width. `ZZZ` is column 18,278 and past every grid we make.
    assert call.kwargs["range"] == f"'{STATE_TAB}'!A500:V"
