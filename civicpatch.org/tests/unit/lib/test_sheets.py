"""Unit tests for the Sheets read/write helpers.

Nothing here reaches Google — the service is a mock, and what is asserted is the A1 notation we
hand it. That is where the risk actually is: a malformed range is rejected wholesale, and the
first time anyone would notice is the first real import.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.sheets import _column_letter, quote_tab, write_columns

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
