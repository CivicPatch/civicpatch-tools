"""A curated sheet's rows into the review queue, one request per jurisdiction.

The same ingest a scrape gets, minus the zip and the images. It stops at ingest:
`AVAILABLE_FOR_REVIEW` is `EXISTS (source_records for this request)`, so writing the sightings
is what raises the review card, and publishing stays the reviewer's existing action.

Spec: `.scratch/2026-08-25-sheet-import-shape.md`.
"""

import asyncio
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone

from core.entry_rows import (
    JURISDICTION,
    ImportRow,
    ImportStatus,
    already_handled,
    jurisdiction_columns,
    parse_rows,
    roster_columns,
    rows_by_jurisdiction,
)
from database.requests import register_sheet_import_request
from database import request_batches
from database.roles import get_roles
from database.source_records import insert_source_records
from pydantic import BaseModel
from lib import sheets
from schemas.imports import ImportPreview
from services import entry_sheet, roster_ingest
from shared.schemas import Role, RoleConfig
from shared.utils.taxonomy import Taxonomy, build_taxonomy

logger = logging.getLogger(__name__)


class SheetRead(BaseModel):
    """What one read of the entry tabs yielded. A model rather than a tuple: the preview
    endpoint wants only `preview`, and discarding two positions to get it invites the throwaway
    names to collide with something."""

    rows: list[ImportRow]
    preview: ImportPreview


class JurisdictionResult(BaseModel):
    """One jurisdiction's outcome, for the run's response and the sheet write-back."""

    jurisdiction_ocdid: str
    status: ImportStatus
    request_id: str | None = None
    people: int = 0
    sightings: int = 0
    posts: int = 0
    error: str | None = None


async def import_rows(
    rows: list[ImportRow],
    user_id: str,
    batch_id: str,
) -> list[JurisdictionResult]:
    """Ingest every jurisdiction the sheet named whose rows have changed, one at a time.

    Jurisdictions are independent, so one failing must not cost the others theirs.

    A locality whose rows all carry a status is left alone — re-reading a sheet nobody has
    touched should do nothing, rather than stack a duplicate card for supersede to clear up
    later. The volunteer decides: clear a row's status cell and it comes back.
    """
    # Read once: a roles edit landing mid-import would classify jurisdictions differently.
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    results = []
    for jurisdiction_ocdid, jurisdiction_rows in rows_by_jurisdiction(rows).items():
        if already_handled(jurisdiction_rows):
            results.append(
                JurisdictionResult(
                    jurisdiction_ocdid=jurisdiction_ocdid,
                    status=ImportStatus.UNCHANGED,
                    people=len(jurisdiction_rows),
                )
            )
            continue
        results.append(
            await _import_jurisdiction(
                jurisdiction_ocdid, jurisdiction_rows, user_id, batch_id, roles, taxonomy
            )
        )
    return results


async def _import_jurisdiction(
    jurisdiction_ocdid: str,
    rows: list[ImportRow],
    user_id: str,
    batch_id: str,
    roles: list[Role],
    taxonomy: Taxonomy,
) -> JurisdictionResult:
    request_id = str(uuid.uuid4())
    try:
        identities = await roster_ingest.published_identities(jurisdiction_ocdid)
        roster, records_by_person = await roster_ingest.reconcile_roster(
            jurisdiction_ocdid,
            [row.sighting.model_dump() for row in rows],
            identities,
            taxonomy,
        )
        await register_sheet_import_request(
            request_id, jurisdiction_ocdid, user_id, batch_id
        )
        sightings = await insert_source_records(
            request_id, jurisdiction_ocdid, records_by_person
        )
    except Exception as e:
        # Fatal for this jurisdiction only. A request registered before the sightings failed is
        # inert — no sightings means no card.
        logger.error(
            f"[{request_id}] {jurisdiction_ocdid}: import failed: {e}", exc_info=True
        )
        return JurisdictionResult(
            jurisdiction_ocdid=jurisdiction_ocdid,
            status=ImportStatus.FAILED,
            error=str(e),
        )

    posts, error = await _derive_posts(
        request_id, jurisdiction_ocdid, roster, roles, taxonomy
    )
    return JurisdictionResult(
        jurisdiction_ocdid=jurisdiction_ocdid,
        status=ImportStatus.IMPORTED if error is None else ImportStatus.PARTIAL,
        request_id=request_id,
        people=len(roster),
        sightings=sightings,
        posts=posts,
        error=error,
    )


async def _derive_posts(
    request_id: str,
    jurisdiction_ocdid: str,
    roster: list[dict],
    roles: list[Role],
    taxonomy: Taxonomy,
) -> tuple[int, str | None]:
    """Reported rather than swallowed: a card without posts still shows its people, so this is
    a `partial`, not a `failed`."""
    try:
        derived = await roster_ingest.derive_and_store_posts(
            request_id, jurisdiction_ocdid, roster, roles, taxonomy
        )
        return len(derived), None
    except Exception as e:
        logger.error(
            f"[{request_id}] {jurisdiction_ocdid}: post derivation failed: {e}",
            exc_info=True,
        )
        return 0, f"people imported, but posts could not be derived: {e}"


def read_rows(rows: list[dict], source_url: str) -> SheetRead:
    """Raw roster rows, parsed, with a preview of what importing them would do.

    Pure, and the only place that decides what "ready" and "blocked" mean. Both callers reach
    it: the one that opens the spreadsheet and the one that is handed rows over HTTP, so the two
    cannot come to different conclusions about the same rows.
    """
    parsed, errors = parse_rows(rows, source_url)

    seen = {row.jurisdiction_ocdid for row in parsed}
    # Blocked whole, never partly: importing six rows of seven proposes a roster missing
    # somebody, which review then reads as a departure.
    blocked = {error.jurisdiction_ocdid for error in errors}
    importable = seen - blocked

    return SheetRead(
        rows=[row for row in parsed if row.jurisdiction_ocdid in importable],
        preview=ImportPreview(
            jurisdictions_ready=sorted(importable),
            jurisdictions_blocked=sorted(blocked),
            rows=len(parsed),
            errors=errors,
        ),
    )


async def read_sheet(spreadsheet_id: str) -> SheetRead:
    """The roster tab, read and previewed.

    Cheap enough to run on every "Check": after the read it is `read_rows`, which is pure. There
    is no deeper dry run — the importer stops at ingest, so the real preview is the review card
    it raises.

    The read goes to a thread: `googleapiclient` is synchronous, and calling it straight from a
    handler would block the event loop for the round trip — the whole API, not just this request.
    """
    roster_rows = await asyncio.to_thread(
        sheets.read_tab, spreadsheet_id, entry_sheet.ROSTER_TAB
    )
    return read_rows(roster_rows, entry_sheet.spreadsheet_url())


async def run_import(
    batch_id: str, rows: list[ImportRow], user_id: str
) -> None:
    """The background half: ingest, report back into the sheet, close the batch.

    `finish` releases the lock, so it must happen either way — including when the write-back
    fails, which must not hold the sheet against every future import.
    """
    status = request_batches.BatchStatus.SUCCEEDED
    error = None
    try:
        results = await import_rows(rows, user_id, batch_id)
        await write_back(results)
    except Exception as e:
        logger.error(f"[{batch_id}] import failed: {e}", exc_info=True)
        status, error = request_batches.BatchStatus.FAILED, str(e)
    await request_batches.finish(batch_id, status, error=error)


async def write_back(results: list[JurisdictionResult]) -> None:
    """Stamp each row and each town with what happened to it.

    Never fatal: the data is already ingested and the review cards already raised, so a Sheets
    outage must not turn a successful import into a failed one. It does leave the volunteer
    without their feedback, which is why it is logged loudly.
    """
    try:
        spreadsheet_id = entry_sheet.spreadsheet_id()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        # Re-read rather than reusing the parse: the tabs are the addressing, so a row inserted
        # since we read would otherwise shift every value onto the wrong line.
        roster, worklist = await asyncio.gather(
            asyncio.to_thread(sheets.read_tab, spreadsheet_id, entry_sheet.ROSTER_TAB),
            asyncio.to_thread(
                sheets.read_tab, spreadsheet_id, entry_sheet.LIVE_JURISDICTIONS_TAB
            ),
        )
        parsed, errors = parse_rows(roster, "")

        by_ocdid = {result.jurisdiction_ocdid: result for result in results}
        imported = {
            ocdid
            for ocdid, result in by_ocdid.items()
            if result.status in (ImportStatus.IMPORTED, ImportStatus.PARTIAL)
        }
        await asyncio.to_thread(
            sheets.write_columns,
            spreadsheet_id,
            entry_sheet.ROSTER_TAB,
            roster_columns(parsed, errors, len(roster), imported, stamp),
        )
        await asyncio.to_thread(
            sheets.write_columns,
            spreadsheet_id,
            entry_sheet.LIVE_JURISDICTIONS_TAB,
            jurisdiction_columns(
                [row.get(JURISDICTION, "") for row in worklist],
                Counter(row.jurisdiction_ocdid for row in parsed),
                {
                    ocdid: (result.status.value, result.error)
                    for ocdid, result in by_ocdid.items()
                },
                stamp,
            ),
        )
    except Exception as e:
        logger.error(f"Failed to write results back to the sheet: {e}", exc_info=True)
