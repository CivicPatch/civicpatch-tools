"""What a pipeline run cost, reported to the cost spreadsheets.

Separate from ingest: it answers a different question, writes to a different place, and its
failure is never allowed to fail a submit whose people are already stored.
"""

import logging

import lib.pipeline_artifacts as artifacts
import lib.sheets as google_sheets_service

COST_BY_REQUEST_SHEET_NAME = "Cost By Request"
LLMS_SHEET_NAME = "Cost LLMs"

logger = logging.getLogger(__name__)


async def send_costs(debug_file_dir: str) -> None:
    logger.info(
        f"Sending costs to Google Sheets from debug file directory: {debug_file_dir}"
    )
    costs_data = artifacts.read_costs(debug_file_dir)

    total_cost_by_request = [list(costs_data.get("total_cost_by_request", {}).values())]
    llm_costs_flattened = [
        list(item.values()) for item in costs_data.get("llm_costs", [])
    ]

    google_sheets_service.update_spreadsheet(
        COST_BY_REQUEST_SHEET_NAME, total_cost_by_request
    )
    google_sheets_service.update_spreadsheet(LLMS_SHEET_NAME, llm_costs_flattened)
