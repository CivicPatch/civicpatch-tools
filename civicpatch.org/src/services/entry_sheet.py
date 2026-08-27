"""The data-entry spreadsheet: which one it is, and what its tabs are called.

Direction-neutral on purpose: the sheet is read *and* written. The importer reads the two entry
tabs; the write-back stamps `status`/`error` onto their rows and refreshes the reference tabs.
Both need to agree on which sheet and which tabs, and neither owns that.

Here rather than in `lib.sheets` because this is a domain fact — that module knows how to talk
to Sheets, not what we keep there.
"""

import environment

# Volunteer-owned.
ROSTER_TAB = "Entry · Roster"
JURISDICTIONS_TAB = "Entry · Jurisdictions"

# App-owned: reference, so a curator can match existing wording rather than invent near-misses.
LIVE_PEOPLE_TAB = "Live · People"
LIVE_POSTS_TAB = "Live · Posts"

# App-owned and hidden: the dropdown source, so an ocdid is never hand-typed.
VOCAB_JURISDICTIONS_TAB = "Vocab · Jurisdictions"


class SheetNotConfigured(Exception):
    pass


def spreadsheet_id() -> str:
    """The one data-entry sheet. Configured, not chosen: civicpatch owns it, so which sheet to
    work against is not a question anyone answers per run."""
    found = environment.get_env_vars().get("ENTRY_SPREADSHEET_ID")
    if not found:
        raise SheetNotConfigured("ENTRY_SPREADSHEET_ID is not set.")
    return found
