"""`ensure_roster_header` — the header row is app-owned now, so it self-heals on every read
instead of needing a human to retype it. Only `lib.sheets` is mocked; it's the boundary.
"""

from unittest.mock import patch

import pytest

from core.entry_rows import REQUIRED_COLUMNS, ROSTER_HEADERS
from services import entry_sheet
from services.sheet_import import ensure_roster_header

_SPREADSHEET_ID = "test-sheet"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_header_row_is_cleared_then_rewritten():
    """Cleared first: a header that shrank must not leave a stale trailing cell behind."""
    with (
        patch("services.sheet_import.sheets.clear_row") as clear_row,
        patch("services.sheet_import.sheets.write_rows") as write_rows,
    ):
        await ensure_roster_header(_SPREADSHEET_ID)

    clear_row.assert_called_once_with(_SPREADSHEET_ID, entry_sheet.ROSTER_TAB, 1, 26)
    write_rows.assert_called_once()
    spreadsheet_id, tab, rows, start_row = write_rows.call_args.args
    assert (spreadsheet_id, tab, start_row) == (_SPREADSHEET_ID, entry_sheet.ROSTER_TAB, 1)
    [written] = rows
    assert len(written) == len(ROSTER_HEADERS)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_required_columns_are_marked_on_the_sheet():
    """A required column reads as required without anyone having to already know the
    contract — the same `*` convention a form uses."""
    with (
        patch("services.sheet_import.sheets.clear_row"),
        patch("services.sheet_import.sheets.write_rows") as write_rows,
    ):
        await ensure_roster_header(_SPREADSHEET_ID)

    [written] = write_rows.call_args.args[2]
    for column, header in zip(ROSTER_HEADERS, written):
        assert header == (f"{column}*" if column in REQUIRED_COLUMNS else column)
