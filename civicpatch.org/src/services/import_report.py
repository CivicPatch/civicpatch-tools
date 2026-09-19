"""Writes the `Live[Import][...]` tab straight after a sheet import.

The only `Live[...]` tab written by the import rather than the sheet sink, and the only one written
before anything is published: it is what the import proposes, for whoever is working the sheet.
"""

import asyncio
import logging
from datetime import datetime, timezone

from core.import_report import (
    REPORT_HEADERS,
    ImportReportRow,
    report_tab,
    report_tabs_in_order,
    row_cells,
    stale_report_tabs,
)
from core.sinks.sheet import widths_for
from lib import sheets
from schemas.sheets import SheetCell
from services import entry_sheet

logger = logging.getLogger(__name__)


async def write_report(rows: list[ImportReportRow]) -> None:
    """Never fatal, like `write_back`: the import has landed whether or not its report does."""
    try:
        spreadsheet_id = entry_sheet.spreadsheet_id()
        tab = report_tab(datetime.now(timezone.utc))
        cells = [[SheetCell(value=header) for header in REPORT_HEADERS]] + [
            row_cells(row) for row in rows
        ]

        titles = await asyncio.to_thread(sheets.tab_titles, spreadsheet_id)
        await asyncio.to_thread(sheets.delete_tabs, spreadsheet_id, stale_report_tabs(titles, tab))
        await asyncio.to_thread(
            sheets.ensure_tab, spreadsheet_id, tab, len(cells), widths_for(REPORT_HEADERS)
        )
        await asyncio.to_thread(sheets.write_cell_rows, spreadsheet_id, tab, cells)

        titles = await asyncio.to_thread(sheets.tab_titles, spreadsheet_id)
        await asyncio.to_thread(
            sheets.reorder_tabs,
            spreadsheet_id,
            [entry_sheet.ROSTER_TAB] + report_tabs_in_order(titles),
        )
    except Exception as e:
        logger.error(f"Failed to write the import report tab: {e}", exc_info=True)
