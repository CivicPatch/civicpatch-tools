"""A curated sheet's rows into the review queue, one request per jurisdiction.

The same ingest a scrape gets, minus the zip and the images. It stops at ingest:
`AVAILABLE_FOR_REVIEW` is `EXISTS (source_records for this request)`, so writing the sightings
is what raises the review card, and publishing stays the reviewer's existing action.

Spec: `.scratch/2026-08-25-sheet-import-shape.md`.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from core.entry_rows import (
    INHERIT,
    REQUIRED_COLUMNS,
    ROSTER_HEADERS,
    ImportRow,
    ImportStatus,
    already_handled,
    parse_rows,
    roster_columns,
    rows_by_jurisdiction,
)
from database.changesets import register_sheet_import_changeset
from database import changeset_batches
from database import memberships
from database.database import get_pool
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
    changeset_id: str | None = None
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


async def _resolve_inherited_labels(
    jurisdiction_ocdid: str, roster: list[dict], records_by_person: dict[str, list[dict]]
) -> tuple[list[dict], dict[str, list[dict]]]:
    """Swap `inherit` for the real label text of the resolved person's current open
    membership, so everything downstream sees it exactly as if the source had sent it —
    ingest's own role/post derivation, and `source_records`, which the review card re-derives
    from on every future view, not only this one.

    By resolved person id, after identity linking (`reconcile_roster` already ran) — not by
    name, which might not match the published spelling.

    A person nothing is found for — new to this import, or between seats — falls back to
    blank, same as never having inherited anything.
    """
    inheriting = [
        person["id"]
        for person in roster
        if any(
            record.get("label") == INHERIT
            for record in records_by_person.get(person["id"], [])
        )
    ]
    if not inheriting:
        return roster, records_by_person

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await memberships.open_source_labels_by_person(
            cur, jurisdiction_ocdid, inheriting
        )

    resolved_roster = [
        {**person, "labels": [found.get(person["id"], "")]}
        if person["id"] in inheriting
        else person
        for person in roster
    ]
    resolved_records = {
        person_id: (
            [{**record, "label": found.get(person_id, "")} for record in records]
            if person_id in inheriting
            else records
        )
        for person_id, records in records_by_person.items()
    }
    return resolved_roster, resolved_records


async def _import_jurisdiction(
    jurisdiction_ocdid: str,
    rows: list[ImportRow],
    user_id: str,
    batch_id: str,
    roles: list[Role],
    taxonomy: Taxonomy,
) -> JurisdictionResult:
    changeset_id = str(uuid.uuid4())
    try:
        identities = await roster_ingest.published_identities(jurisdiction_ocdid)
        roster, records_by_person = await roster_ingest.reconcile_roster(
            jurisdiction_ocdid,
            [row.sighting.model_dump() for row in rows],
            identities,
            taxonomy,
        )
        roster, records_by_person = await _resolve_inherited_labels(
            jurisdiction_ocdid, roster, records_by_person
        )
        await register_sheet_import_changeset(
            changeset_id, jurisdiction_ocdid, user_id, batch_id
        )
        sightings = await insert_source_records(
            changeset_id, jurisdiction_ocdid, records_by_person
        )
    except Exception as e:
        # Fatal for this jurisdiction only. A request registered before the sightings failed is
        # inert — no sightings means no card.
        logger.error(
            f"[{changeset_id}] {jurisdiction_ocdid}: import failed: {e}", exc_info=True
        )
        return JurisdictionResult(
            jurisdiction_ocdid=jurisdiction_ocdid,
            status=ImportStatus.FAILED,
            error=str(e),
        )

    posts, error = await _derive_posts(
        changeset_id, jurisdiction_ocdid, roster, roles, taxonomy
    )
    return JurisdictionResult(
        jurisdiction_ocdid=jurisdiction_ocdid,
        status=ImportStatus.IMPORTED if error is None else ImportStatus.PARTIAL,
        changeset_id=changeset_id,
        people=len(roster),
        sightings=sightings,
        posts=posts,
        error=error,
    )


async def _derive_posts(
    changeset_id: str,
    jurisdiction_ocdid: str,
    roster: list[dict],
    roles: list[Role],
    taxonomy: Taxonomy,
) -> tuple[int, str | None]:
    """How many seats this import projects. Nothing is written — publishing creates them.

    Reported rather than swallowed: a card without posts still shows its people, so this is
    a `partial`, not a `failed`."""
    try:
        derived = await roster_ingest.derive_posts(roster, roles, taxonomy)
        return len(derived), None
    except Exception as e:
        logger.error(
            f"[{changeset_id}] {jurisdiction_ocdid}: post derivation failed: {e}",
            exc_info=True,
        )
        return 0, f"people imported, but posts could not be derived: {e}"


def read_rows(rows: list[dict]) -> SheetRead:
    """Raw roster rows, parsed, with a preview of what importing them would do.

    Pure, and the only place that decides what "ready" and "blocked" mean. Both callers reach
    it: the one that opens the spreadsheet and the one that is handed rows over HTTP, so the two
    cannot come to different conclusions about the same rows.
    """
    parsed, errors = parse_rows(rows)

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


def _header_text(column: str) -> str:
    """A required column reads as required on the sheet itself — `*`, the same convention a
    form uses — without anyone having to already know the contract. `lib.csv.rows_from_table`
    strips it back off before matching a cell to this name."""
    return f"{column}*" if column in REQUIRED_COLUMNS else column


async def ensure_roster_header(spreadsheet_id: str) -> None:
    """Assert the roster tab's header row matches `ROSTER_HEADERS`, so a contract change never
    needs a human to retype it — only row 1: data rows are the volunteer's, never rewritten.

    Cleared first, bounded to a generous width: a header that shrank must not leave a stale
    trailing cell from a wider one it used to be.
    """
    await asyncio.to_thread(
        sheets.clear_row, spreadsheet_id, entry_sheet.ROSTER_TAB, 1, 26
    )
    await asyncio.to_thread(
        sheets.write_rows,
        spreadsheet_id,
        entry_sheet.ROSTER_TAB,
        [[_header_text(column) for column in ROSTER_HEADERS]],
        1,
    )


async def read_sheet(spreadsheet_id: str) -> SheetRead:
    """The roster tab, read and previewed.

    There is no deeper dry run — the importer stops at ingest, so the real preview is the review
    card it raises.

    The read goes to a thread: `googleapiclient` is synchronous, and calling it straight from a
    handler would block the event loop for the round trip — the whole API, not just this request.
    """
    await ensure_roster_header(spreadsheet_id)
    roster_rows = await asyncio.to_thread(
        sheets.read_tab, spreadsheet_id, entry_sheet.ROSTER_TAB
    )
    return read_rows(roster_rows)


async def run_import(
    batch_id: str, rows: list[ImportRow], user_id: str
) -> None:
    """The background half: ingest, report back into the sheet, close the batch.

    `finish` releases the lock, so it must happen either way — including when the write-back
    fails, which must not hold the sheet against every future import.
    """
    status = changeset_batches.BatchStatus.SUCCEEDED
    error = None
    try:
        results = await import_rows(rows, user_id, batch_id)
        # A jurisdiction failing is not an exception here — `_import_jurisdiction` catches its
        # own and reports it in the result — so without this the batch reads `succeeded` with
        # no hint that a town silently failed to import at all.
        failed = [
            result for result in results if result.status is ImportStatus.FAILED
        ]
        if failed:
            status = changeset_batches.BatchStatus.FAILED
            error = "; ".join(
                f"{result.jurisdiction_ocdid}: {result.error}" for result in failed
            )
        await write_back(results)
    except Exception as e:
        logger.error(f"[{batch_id}] import failed: {e}", exc_info=True)
        status, error = changeset_batches.BatchStatus.FAILED, str(e)
    await changeset_batches.finish(batch_id, status, error=error)


async def write_back(results: list[JurisdictionResult]) -> None:
    """Stamp each roster row with what happened to it.

    The roster tab only. `Live[Jurisdictions]` is the sheet sync's to own — two writers on one
    tab raced, and with every state listed a per-town report described 9,464 rows to say
    something about twenty.

    Never fatal: the data is already ingested and the review cards already raised, so a Sheets
    outage must not turn a successful import into a failed one. It does leave the volunteer
    without their feedback, which is why it is logged loudly.
    """
    try:
        spreadsheet_id = entry_sheet.spreadsheet_id()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        # Re-read rather than reusing the parse: the tab is the addressing, so a row inserted
        # since we read would otherwise shift every value onto the wrong line.
        roster = await asyncio.to_thread(
            sheets.read_tab, spreadsheet_id, entry_sheet.ROSTER_TAB
        )
        parsed, errors = parse_rows(roster)

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
            roster_columns(roster, parsed, errors, imported, stamp),
        )
    except Exception as e:
        logger.error(f"Failed to write results back to the sheet: {e}", exc_info=True)
