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
from enum import StrEnum

from core.entry_rows import (
    JURISDICTION,
    ImportRow,
    jurisdiction_columns,
    parse_rows,
    ready_jurisdictions,
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


class Disposition(StrEnum):
    IMPORTED = "imported"
    # People stored, posts not. Re-derivable from the sightings, so not a failure.
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


class SheetRead(BaseModel):
    """What one read of the entry tabs yielded. A model rather than a tuple: the preview
    endpoint wants only `preview`, and discarding two positions to get it invites the throwaway
    names to collide with something."""

    rows: list[ImportRow]
    ready: set[str]
    preview: ImportPreview


class JurisdictionResult(BaseModel):
    """One jurisdiction's outcome, for the run's response and the sheet write-back."""

    jurisdiction_ocdid: str
    disposition: Disposition
    request_id: str | None = None
    people: int = 0
    sightings: int = 0
    posts: int = 0
    error: str | None = None


async def import_rows(
    rows: list[ImportRow],
    ready: set[str],
    user_id: str,
    batch_id: str,
) -> list[JurisdictionResult]:
    """Ingest every ready jurisdiction, one at a time.

    Jurisdictions are independent, so one failing must not cost the others theirs.
    """
    # Read once: a roles edit landing mid-import would classify jurisdictions differently.
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    results = []
    for jurisdiction_ocdid, jurisdiction_rows in rows_by_jurisdiction(rows).items():
        if jurisdiction_ocdid not in ready:
            results.append(
                JurisdictionResult(
                    jurisdiction_ocdid=jurisdiction_ocdid,
                    disposition=Disposition.SKIPPED,
                    error="not marked ready",
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
            disposition=Disposition.FAILED,
            error=str(e),
        )

    posts, error = await _derive_posts(
        request_id, jurisdiction_ocdid, roster, roles, taxonomy
    )
    return JurisdictionResult(
        jurisdiction_ocdid=jurisdiction_ocdid,
        disposition=Disposition.IMPORTED if error is None else Disposition.PARTIAL,
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


async def read_sheet(spreadsheet_id: str) -> SheetRead:
    """Both entry tabs, parsed, with a preview of what an import would do.

    Cheap enough to run on every "Check": after the two reads it is `parse_rows`, which is pure.
    There is no deeper dry run — the importer stops at ingest, so the real preview is the review
    card it raises.

    The reads go to a thread: `googleapiclient` is synchronous, and calling it straight from a
    handler would block the event loop for the round trip — the whole API, not just this request.
    """
    source_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    roster_rows, worklist_rows = await asyncio.gather(
        asyncio.to_thread(sheets.read_tab, spreadsheet_id, entry_sheet.ROSTER_TAB),
        asyncio.to_thread(
            sheets.read_tab, spreadsheet_id, entry_sheet.JURISDICTIONS_TAB
        ),
    )
    rows, errors = parse_rows(roster_rows, source_url)
    ready = ready_jurisdictions(worklist_rows)

    seen = {row.jurisdiction_ocdid for row in rows}
    # Blocked whole, never partly: importing six rows of seven proposes a roster missing
    # somebody, which review then reads as a departure.
    blocked = {error.jurisdiction_ocdid for error in errors}
    importable = ready - blocked

    return SheetRead(
        rows=[row for row in rows if row.jurisdiction_ocdid in importable],
        ready=importable,
        preview=ImportPreview(
            jurisdictions_ready=sorted(importable & seen),
            jurisdictions_blocked=sorted(blocked),
            jurisdictions_skipped=sorted(seen - ready),
            rows=len(rows),
            errors=errors,
        ),
    )


async def run_import(
    batch_id: str, rows: list[ImportRow], ready: set[str], user_id: str
) -> None:
    """The background half: ingest, report back into the sheet, close the batch.

    `finish` releases the lock, so it must happen either way — including when the write-back
    fails, which must not hold the sheet against every future import.
    """
    status = request_batches.BatchStatus.SUCCEEDED
    error = None
    try:
        results = await import_rows(rows, ready, user_id, batch_id)
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
                sheets.read_tab, spreadsheet_id, entry_sheet.JURISDICTIONS_TAB
            ),
        )
        parsed, errors = parse_rows(roster, "")

        by_ocdid = {result.jurisdiction_ocdid: result for result in results}
        imported = {
            ocdid
            for ocdid, result in by_ocdid.items()
            if result.disposition
            in (Disposition.IMPORTED, Disposition.PARTIAL)
        }
        skipped = {
            ocdid
            for ocdid, result in by_ocdid.items()
            if result.disposition is Disposition.SKIPPED
        }

        await asyncio.to_thread(
            sheets.write_columns,
            spreadsheet_id,
            entry_sheet.ROSTER_TAB,
            roster_columns(parsed, errors, len(roster), imported, skipped, stamp),
        )
        await asyncio.to_thread(
            sheets.write_columns,
            spreadsheet_id,
            entry_sheet.JURISDICTIONS_TAB,
            jurisdiction_columns(
                [row.get(JURISDICTION, "") for row in worklist],
                Counter(row.jurisdiction_ocdid for row in parsed),
                {
                    ocdid: (result.disposition.value, result.error)
                    for ocdid, result in by_ocdid.items()
                },
                stamp,
            ),
        )
    except Exception as e:
        logger.error(f"Failed to write results back to the sheet: {e}", exc_info=True)
