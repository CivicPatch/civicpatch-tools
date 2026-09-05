import base64

import googleapiclient.discovery
from google.oauth2 import service_account
import environment
from lib.csv import rows_from_table

def quote_tab(tab: str) -> str:
    """A tab name as A1 notation accepts it.

    Every entry tab has a space and a `·` in it, and A1 notation needs any name that is not a
    bare word in single quotes — unquoted, the API rejects the range outright. Quoting a name
    that did not need it is harmless, so this is unconditional. Internal quotes double.
    """
    return "'" + tab.replace("'", "''") + "'"


# https://developers.google.com/workspace/sheets/api/guides/values#append_values
# https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values#resource-valuerange
def read_tab(spreadsheet_id: str, tab: str) -> list[dict]:
    """One tab's rows, keyed by its header.

    Authenticated rather than the public `/export?format=csv` trick: the sheet must be shared for
    the write-back anyway, so it never has to be readable by anyone holding the url.

    `UNFORMATTED_VALUE` so a phone number stays what the cell holds rather than what Sheets
    decided to render.
    """
    service = get_service()
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=quote_tab(tab),
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    return rows_from_table(response.get("values", []))


def read_header(spreadsheet_id: str, tab: str) -> list[str]:
    """The tab's first row, lowercased — column positions, which `read_tab` throws away."""
    response = (
        get_service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{quote_tab(tab)}!1:1")
        .execute()
    )
    values = response.get("values", [[]])
    return [str(name or "").strip().lower() for name in (values[0] if values else [])]


def _column_letter(index: int) -> str:
    letters = ""
    while True:
        index, remainder = divmod(index, 26)
        letters = chr(ord("A") + remainder) + letters
        if index == 0:
            return letters
        index -= 1


def write_columns(spreadsheet_id: str, tab: str, columns: dict[str, list]) -> int:
    """Overwrite whole columns below the header. Returns how many cells were written.

    Whole columns rather than the cells that changed: a row that errored last run and is fine
    now needs its `error` cleared, and a sparse update would leave the stale text sitting there.

    `RAW`, never `USER_ENTERED` — the latter reinterprets what it is given, so a phone number
    becomes an integer and `03/04` becomes a date.
    """
    header = read_header(spreadsheet_id, tab)
    data = []
    for name, values in columns.items():
        if name not in header:
            raise ValueError(f"{tab} has no column {name!r}")
        # A header-only tab yields empty columns, and `C2:C1` is a range the API refuses.
        if not values:
            continue
        letter = _column_letter(header.index(name))
        data.append(
            {
                "range": f"{quote_tab(tab)}!{letter}2:{letter}{len(values) + 1}",
                "values": [[value] for value in values],
            }
        )

    if not data:
        return 0
    response = (
        get_service()
        .spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data},
        )
        .execute()
    )
    return response.get("totalUpdatedCells", 0)


# A sheet created by `addSheet` is 1000 rows, and `values.update` refuses a range past the grid
# rather than growing it — only `values.append` grows. Texas is 5,844 rows, so a tab left at the
# default would 400 on its first write while every small state passed.
_MINIMUM_ROWS = 2

# Warning-only, like the Apps Script's. A hard lock needs every volunteer named as an exception
# on every range, and a new volunteer would silently lose access.
_PROTECTION_SUFFIX = " (app-owned)"


def _batch_update(service, spreadsheet_id: str, requests: list) -> dict:
    if not requests:
        return {}
    return (
        service.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
        .execute()
    )


def _sheet(service, spreadsheet_id: str, tab: str) -> dict | None:
    """One tab's properties and protections, or None when it does not exist yet."""
    response = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields=(
                "sheets(properties(sheetId,title,gridProperties),"
                "protectedRanges(protectedRangeId,description))"
            ),
        )
        .execute()
    )
    for sheet in response.get("sheets", []):
        if sheet.get("properties", {}).get("title") == tab:
            return sheet
    return None


def _grid_requests(sheet: dict, rows: int, columns: int) -> list:
    """Grow the grid to fit, never shrink it. Shrinking would delete cells mid-sync, and the
    trim after the write is what removes stale rows."""
    properties = sheet["properties"]
    grid = properties.get("gridProperties", {})
    wanted = {
        "rowCount": max(rows, grid.get("rowCount", 0)),
        "columnCount": max(columns, grid.get("columnCount", 0)),
    }
    if wanted["rowCount"] == grid.get("rowCount") and wanted["columnCount"] == grid.get(
        "columnCount"
    ):
        return []
    return [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": properties["sheetId"], "gridProperties": wanted},
                "fields": "gridProperties.rowCount,gridProperties.columnCount",
            }
        }
    ]


def _column_width_requests(sheet_id: int, widths: list[int]) -> list:
    """One request per column, sent with the tab that was just created — it rides along in a
    batchUpdate that already exists, so it costs no extra round trip."""
    return [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": index,
                    "endIndex": index + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        }
        for index, width in enumerate(widths)
    ]


def _freeze_header_request(sheet_id: int) -> dict:
    """Keeps the header visible while scrolling nine thousand rows."""
    return {
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }
    }


def _text_format_request(sheet_id: int) -> dict:
    """Plain text for the whole tab. Redundant while writes are `RAW`, which stores what it is
    given — but it is one request, and it is what stops `2024` becoming a number if anyone ever
    reaches for `USER_ENTERED`."""
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "TEXT"}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _protection_requests(sheet: dict, tab: str) -> list:
    """Protect the whole tab, once. Whole-sheet rather than a bounded range so it never needs
    resizing when the grid grows, and skipped when already present so re-runs do not stack
    duplicate protections."""
    description = tab + _PROTECTION_SUFFIX
    for protection in sheet.get("protectedRanges", []):
        if protection.get("description") == description:
            return []
    return [
        {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {"sheetId": sheet["properties"]["sheetId"]},
                    "description": description,
                    "warningOnly": True,
                }
            }
        }
    ]


def ensure_tab(
    spreadsheet_id: str, tab: str, row_count: int, widths: list[int]
) -> int:
    """Make `tab` exist, big enough to hold `row_count` rows, formatted and protected.

    Returns the grid's row count afterwards, which the caller needs to know whether a trim is
    even addressable — every range is validated against the grid, so clearing from a row past
    the end is an error rather than a no-op.

    Called before every write rather than once at setup: a state's row count grows, and the
    backend is the only thing that knows a new state's tab is needed at all.
    """
    service = get_service()
    sheet = _sheet(service, spreadsheet_id, tab)
    rows = max(row_count, _MINIMUM_ROWS)
    column_count = len(widths)

    if sheet is None:
        created = _batch_update(
            service,
            spreadsheet_id,
            [
                {
                    "addSheet": {
                        "properties": {
                            "title": tab,
                            "gridProperties": {
                                "rowCount": rows,
                                "columnCount": column_count,
                            },
                        }
                    }
                }
            ],
        )
        properties = created["replies"][0]["addSheet"]["properties"]
        sheet = {"properties": properties, "protectedRanges": []}
        sheet_id = properties["sheetId"]
        appearance = [
            _text_format_request(sheet_id),
            _freeze_header_request(sheet_id),
        ] + _column_width_requests(sheet_id, widths)
    else:
        # Set once, on the tab we created. Re-asserting it nightly was a write request per tab
        # that changed nothing — and these tabs are app-owned, so nobody's edits are being
        # tidied up by it.
        appearance = []

    _batch_update(
        service,
        spreadsheet_id,
        _grid_requests(sheet, rows, column_count)
        + appearance
        + _protection_requests(sheet, tab),
    )
    # `_grid_requests` grows but never shrinks, so this is the same max it applied.
    existing = sheet["properties"].get("gridProperties", {}).get("rowCount", 0)
    return max(rows, existing)


def write_rows(spreadsheet_id: str, tab: str, rows: list[list], start_row: int) -> int:
    """Write a block of rows at `start_row` (1-based). Returns how many cells were written.

    `RAW`, never `USER_ENTERED` — the latter reinterprets what it is given, so a phone number
    becomes an integer, `2024` becomes a number and a leading `=` becomes a live formula.
    """
    if not rows:
        return 0
    last_column = _column_letter(max(len(row) for row in rows) - 1)
    end_row = start_row + len(rows) - 1
    response = (
        get_service()
        .spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=f"{quote_tab(tab)}!A{start_row}:{last_column}{end_row}",
            valueInputOption="RAW",
            body={"values": rows},
        )
        .execute()
    )
    return response.get("updatedCells", 0)


def clear_rows_from(
    spreadsheet_id: str, tab: str, start_row: int, column_count: int
) -> None:
    """Drop everything from `start_row` down — the trim after a write.

    Bounded to the columns the tab actually has, and open-ended only on rows. Naming a column
    past the grid is rejected exactly as `values.update` rejects a row past it, and `ZZZ` is
    column 18,278.

    Trimming afterwards rather than clearing first is deliberate: a clear that lands while a
    later chunk fails would leave the tab reading as zero officials until a retry, and a stale
    tail is a much better failure than an empty tab.
    """
    last_column = _column_letter(column_count - 1)
    (
        get_service()
        .spreadsheets()
        .values()
        .clear(
            spreadsheetId=spreadsheet_id,
            range=f"{quote_tab(tab)}!A{start_row}:{last_column}",
            body={},
        )
        .execute()
    )


# Constant, not configuration: the token endpoint is the same for every service account, and
# the key file carries it too.
_TOKEN_URI = "https://oauth2.googleapis.com/token"


class SheetsNotConfigured(Exception):
    """No usable Google credentials. Distinct from a sheet we cannot read: nothing was sent."""


def get_credentials():
    env = environment.get_env_vars()
    if not env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"]:
        raise SheetsNotConfigured("GOOGLE_SHEETS_PRIVATE_KEY_BASE64 is not set.")

    if not env["GOOGLE_SHEETS_CLIENT_EMAIL"]:
        raise SheetsNotConfigured("GOOGLE_SHEETS_CLIENT_EMAIL is not set.")

    scopes =  ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        private_key = base64.b64decode(
            env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"], validate=True
        ).decode("utf-8")
    except Exception as e:
        # A placeholder like NO_KEY_PROVIDED lands here, and it is a deployment problem rather
        # than an unreadable sheet — saying "share it with us" sends people chasing the wrong
        # thing entirely.
        raise SheetsNotConfigured(
            f"GOOGLE_SHEETS_PRIVATE_KEY_BASE64 is not valid base64: {e}"
        ) from e

    account_info = {
        "private_key": private_key,
        "client_email": env["GOOGLE_SHEETS_CLIENT_EMAIL"],
        "token_uri": _TOKEN_URI,
    }

    credentials = service_account.Credentials.from_service_account_info(account_info, scopes=scopes)
    return credentials

def get_service():
    credentials = get_credentials()
    service = googleapiclient.discovery.build('sheets', 'v4', credentials=credentials)
    return service