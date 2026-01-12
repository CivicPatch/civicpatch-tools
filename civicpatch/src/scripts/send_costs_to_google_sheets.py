#!/usr/bin/env python3
import os
import sys
import json
from services import google_sheets_service
from shared.utils import data_path_utils

GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
GOOGLE_SHEETS_PRIVATE_KEY = os.getenv("GOOGLE_SHEETS_PRIVATE_KEY", "")
GOOGLE_SHEETS_CLIENT_EMAIL = os.getenv("GOOGLE_SHEETS_CLIENT_EMAIL", "")
GOOGLE_SHEETS_TOKEN_URI = os.getenv("GOOGLE_SHEETS_TOKEN_URI", "")

COST_BY_REQUEST_SHEET_NAME = "Cost By Request"
LLMS_SHEET_NAME = "Cost LLMs"
SEARCH_ENGINES_SHEET_NAME = "Cost Search Engines"
STORAGE_SHEET_NAME = "Cost Storage"

def send_costs_to_google_sheets(jurisdiction_ocdid: str):
    data_source_path = data_path_utils.get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    costs_file_path = os.path.join(data_source_path, "costs.json")

    with open(costs_file_path, "r") as f:
        costs_data = json.load(f)

    total_cost_by_request = [list(costs_data.get("total_cost_by_request", {}).values())]
    llm_costs_flattened = [list(item.values()) for item in costs_data.get("llm_costs", [])]
    search_engine_costs_flattened = [list(item.values()) for item in costs_data.get("search_engine_costs", [])]
    storage_costs_flattened = [list(item.values()) for item in costs_data.get("storage_costs", [])]

    google_sheets_service.update_spreadsheet(COST_BY_REQUEST_SHEET_NAME, total_cost_by_request)
    google_sheets_service.update_spreadsheet(LLMS_SHEET_NAME, llm_costs_flattened)
    google_sheets_service.update_spreadsheet(SEARCH_ENGINES_SHEET_NAME, search_engine_costs_flattened)
    google_sheets_service.update_spreadsheet(STORAGE_SHEET_NAME, storage_costs_flattened)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python send_costs_to_google_sheets.py <jurisdiction_ocdid>")
        sys.exit(1)

    missing_vars = [var_name for var_name, var in [
        ("GOOGLE_SHEETS_SPREADSHEET_ID", GOOGLE_SHEETS_SPREADSHEET_ID),
        ("GOOGLE_SHEETS_PRIVATE_KEY", GOOGLE_SHEETS_PRIVATE_KEY),
        ("GOOGLE_SHEETS_CLIENT_EMAIL", GOOGLE_SHEETS_CLIENT_EMAIL),
        ("GOOGLE_SHEETS_TOKEN_URI", GOOGLE_SHEETS_TOKEN_URI),
    ] if not var]   

    if len(missing_vars) > 0:
        print(f"Error: The following environment variables are not set: {', '.join(missing_vars)}")
        sys.exit(1)

    jurisdiction_ocdid = sys.argv[1]
    send_costs_to_google_sheets(jurisdiction_ocdid)
