"""Keeping the `jurisdictions` table in step with open-data — the list of places, inbound.

Jurisdictions only, and that is the whole scope: `classify_path` matches
`data_source/<state>/<level>/jurisdictions.yml` and nothing else, because the people half went
with migration 150 (`data/**` is rendered *from* the database now). Direction is in the name
now — `source:` reads, `sink:` writes — so *sync*, which used to carry it by convention, is
gone from both sides.

Not to be confused with *ingest*, which is a scrape's uploaded artifacts becoming people rows —
that happens in the API on artifact upload, not on any queue.

Split out of the old single `activities.py` on 2026-09-05 so this worker's process does not
import pyarrow, boto3 and gspread for work it never does.
"""

import services.sources.open_data as open_data_source
from services import entry_sheet
from temporalio import activity


@activity.defn
async def read_open_data_jurisdictions_activity() -> None:
    await open_data_source.read_all()
    # Its own workflow, not an activity here: this schedule is SKIP-overlap, so a Sheets write
    # retrying forever would block every later read.
    #
    # avoid circular import: the client imports the workflows module, which imports this one
    import lib.temporal.client as temporal_client

    if entry_sheet.is_configured():
        await temporal_client.enqueue_write_sheet_jurisdictions()
