import os
import base64
from google.oauth2 import service_account
import googleapiclient.discovery
import environment

# https://developers.google.com/workspace/sheets/api/guides/values#append_values
# https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values#resource-valuerange
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

def get_credentials():
    env = environment.get_env_vars()
    if env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"] is None or env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"] == "":
        raise ValueError("GOOGLE_SHEETS_PRIVATE_KEY_BASE64 environment variable is not set.")

    if env["GOOGLE_SHEETS_CLIENT_EMAIL"] is None or env["GOOGLE_SHEETS_CLIENT_EMAIL"] == "":
        raise ValueError("GOOGLE_SHEETS_CLIENT_EMAIL environment variable is not set.")

    if env["GOOGLE_SHEETS_TOKEN_URI"] is None or env["GOOGLE_SHEETS_TOKEN_URI"] == "":
        raise ValueError("GOOGLE_SHEETS_TOKEN_URI environment variable is not set.")

    scopes =  ["https://www.googleapis.com/auth/spreadsheets"]
    account_info = {
        "private_key": base64.b64decode(env["GOOGLE_SHEETS_PRIVATE_KEY_BASE64"]).decode("utf-8"),
        "client_email": env["GOOGLE_SHEETS_CLIENT_EMAIL"],
        "token_uri": env["GOOGLE_SHEETS_TOKEN_URI"],
    }

    credentials = service_account.Credentials.from_service_account_info(account_info, scopes=scopes)
    return credentials

def get_service():
    credentials = get_credentials()
    service = googleapiclient.discovery.build('sheets', 'v4', credentials=credentials)
    return service