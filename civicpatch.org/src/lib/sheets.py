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


def update_spreadsheet(sheet_name, values):
    env = environment.get_env_vars()
    spreadsheet_id = env["GOOGLE_SHEETS_SPREADSHEET_ID"]
    if spreadsheet_id is None or spreadsheet_id == "":
        raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID environment variable is not set.")
    service = get_service()

    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values}
        ).execute()

    num_rows_updated = result.get('updates').get('updatedRows')
    print(f"{sheet_name}: Number of rows updated: {num_rows_updated}")

# Constant, not configuration: the token endpoint is the same for every service account, and
# the key file carries it too.
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_credentials():
    env = environment.get_env_vars()
    if env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"] is None or env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"] == "":
        raise ValueError("GOOGLE_SHEETS_PRIVATE_KEY_BASE64 environment variable is not set.")

    if env["GOOGLE_SHEETS_CLIENT_EMAIL"] is None or env["GOOGLE_SHEETS_CLIENT_EMAIL"] == "":
        raise ValueError("GOOGLE_SHEETS_CLIENT_EMAIL environment variable is not set.")

    scopes =  ["https://www.googleapis.com/auth/spreadsheets"]
    account_info = {
        "private_key": base64.b64decode(env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"]).decode("utf-8"),
        "client_email": env["GOOGLE_SHEETS_CLIENT_EMAIL"],
        "token_uri": _TOKEN_URI,
    }

    credentials = service_account.Credentials.from_service_account_info(account_info, scopes=scopes)
    return credentials

def get_service():
    credentials = get_credentials()
    service = googleapiclient.discovery.build('sheets', 'v4', credentials=credentials)
    return service