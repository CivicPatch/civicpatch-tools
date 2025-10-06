import os
from google.oauth2 import service_account
import googleapiclient.discovery

# https://developers.google.com/workspace/sheets/api/guides/values#append_values
# https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values#resource-valuerange
def update_spreadsheet(sheet_name, values):
    if os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") is None or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") == "":
        raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID environment variable is not set.")
    
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    service = get_service()

    result = service.spreadsheets(sheet_name)
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [["Hello from Python!"]]}
        ).execute()



def get_credentials(): 
    if os.getenv("GOOGLE_SHEETS_PRIVATE_KEY") is None or os.getenv("GOOGLE_SHEETS_PRIVATE_KEY") == "":
        raise ValueError("GOOGLE_SHEETS_PRIVATE_KEY environment variable is not set.")

    if os.getenv("GOOGLE_SHEETS_CLIENT_EMAIL") is None or os.getenv("GOOGLE_SHEETS_CLIENT_EMAIL") == "":
        raise ValueError("GOOGLE_SHEETS_CLIENT_EMAIL environment variable is not set.")
    
    if os.getenv("GOOGLE_SHEETS_TOKEN_URI") is None or os.getenv("GOOGLE_SHEETS_TOKEN_URI") == "":
        raise ValueError("GOOGLE_SHEETS_TOKEN_URI environment variable is not set.")

    scopes =  ["https://www.googleapis.com/auth/drive.file"]
    account_info = {
        "private_key": os.getenv("GOOGLE_SHEETS_PRIVATE_KEY"),
        "client_email": os.getenv("GOOGLE_SHEETS_CLIENT_EMAIL"),
        "token_uri": os.getenv("GOOGLE_SHEETS_TOKEN_URI"),
    }

    credentials = service_account.Credentials.from_service_account_info(account_info, scopes=scopes)
    return credentials

def get_service():
    credentials = get_credentials()
    service = googleapiclient.discovery.build('sheets', 'v4', credentials=credentials)
    return service