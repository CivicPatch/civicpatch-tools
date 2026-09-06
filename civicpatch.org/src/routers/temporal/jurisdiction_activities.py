"""Keeping the `jurisdictions` table in step with open-data — the list of places, inbound.

Jurisdictions only, and that is the whole scope: `classify_path` matches
`data_source/<state>/<level>/jurisdictions.yml` and nothing else, because the people half went
with migration 150 (`data/**` is rendered *from* the database now). This is the one direction
`AGENTS.md:40` reserves the word *sync* for; everything that writes outward is `sink_activities`.

Not to be confused with *ingest*, which is a scrape's uploaded artifacts becoming people rows —
that happens in the API on artifact upload, not on any queue.

Split out of the old single `activities.py` on 2026-09-05 so this worker's process does not
import pyarrow, boto3 and gspread for work it never does.
"""

import services.open_data_sync as data_sync
from services import entry_sheet
from temporalio import activity


@activity.defn
async def od_sync_activity() -> None:
    await data_sync.sync_all()
    # Its own workflow, not an activity here: this schedule is SKIP-overlap, so a Sheets write
    # retrying forever would block every later sync.
    #
    # avoid circular import: the client imports the workflows module, which imports this one
    import lib.temporal.client as temporal_client

    if entry_sheet.is_configured():
        await temporal_client.enqueue_jurisdictions_sheet_sync()


@activity.defn
async def od_sync_targeted_activity(jurisdiction_ocdids: list[str]) -> None:
    await data_sync.sync_by_ocdids(jurisdiction_ocdids)
