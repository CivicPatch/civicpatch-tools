"""`ensure_roster_header` — the header row is app-owned now, so it self-heals on every read
instead of needing a human to retype it. Only `lib.sheets` is mocked; it's the boundary.
"""

from unittest.mock import patch

import pytest

from core.entry_rows import ROSTER_HEADERS
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
    write_rows.assert_called_once_with(
        _SPREADSHEET_ID, entry_sheet.ROSTER_TAB, [list(ROSTER_HEADERS)], 1
    )
