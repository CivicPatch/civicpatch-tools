"""The data-entry spreadsheet: which one it is, and what the volunteer's tab is called.

Here rather than in `lib.sheets` because this is a domain fact — that module knows how to talk
to Sheets, not what we keep there.
"""

import environment

# Volunteer-owned.
ROSTER_TAB = "Entry[Roster]"

# The app-owned tabs are `services.roster_sheet`'s: it names them per state and is their only
# writer. Nothing here reads them.


class SheetNotConfigured(Exception):
    pass


def spreadsheet_url() -> str:
    """Where a volunteer goes to look at or fix the rows. One place builds it, so the link on
    the import page and the `source_url` stamped onto every sighting cannot disagree."""
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id()}"


def is_configured() -> bool:
    """Whether there is a sheet to write to at all.

    Checked before enqueueing, not inside the workflow: an unconfigured deploy would otherwise
    pile up a permanently-failing workflow per sweep.
    """
    return bool(environment.get_env_vars().get("ENTRY_SPREADSHEET_ID"))


def spreadsheet_id() -> str:
    """The one data-entry sheet. Configured, not chosen: civicpatch owns it, so which sheet to
    work against is not a question anyone answers per run. docker-compose defaults it for dev."""
    found = environment.get_env_vars().get("ENTRY_SPREADSHEET_ID")
    if not found:
        raise SheetNotConfigured("ENTRY_SPREADSHEET_ID is not set.")
    return found
