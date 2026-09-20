"""A curated sheet's rows into one open changeset per jurisdiction.

The same ingest a scrape gets, minus the zip and the images. It stops at ingest: the changesets
are published or dismissed on the import's batch page, never from the review pool.

Spec: `.scratch/2026-08-25-sheet-import-shape.md`.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from core.sheet_import_columns import (
    by_row,
    merge_jurisdiction_notes,
    published_other_names_by_person,
    roster_columns,
)
from core.sheet_import_rows import (
    PUBLISHED_OTHER_NAMES,
    REQUIRED_COLUMNS,
    ROSTER_HEADERS,
    ImportRow,
    ImportStatus,
    JurisdictionIndex,
    RowError,
    already_handled,
    build_jurisdiction_index,
    parse_rows,
    resolve_jurisdiction,
    rows_by_jurisdiction,
)
from core.import_report import ImportReportRow, report_rows
from core.roster_diff import (
    ProposalCounts,
    likely_same_people,
    person_diffs,
    person_notes,
    proposal_counts,
)
from core.source_sites import SiteIndex, build_site_index
from database.changesets import register_sheet_import_changeset, set_proposal_counts
from database import changeset_batches, dismissals
from database import sites as sites_db
from database.jurisdictions import get_jurisdiction_geoids
from database.people import get_rosters_by_jurisdiction
from database.roles import get_roles
from database.source_records import insert_source_records
from pydantic import BaseModel
from lib import sheets
from lib.csv import READ_ONLY_MARKER, REQUIRED_MARKER
from schemas.imports import ImportPreview
from services import entry_sheet, import_report, roster_ingest
from services.review_proposal import proposals_for_requests
from services.roster import proposed_roster
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
    # By `row_key`'s lowercased name.
    notes: dict[str, str] = {}
    published_other_names: dict[str, str] = {}
    report: list[ImportReportRow] = []


class ImportChanges(BaseModel):
    """What one import changes, from one read so the parts cannot disagree. Row values are
    keyed by `row_key`'s lowercased name."""

    notes: dict[str, str] = {}
    published_other_names: dict[str, str] = {}
    report: list[ImportReportRow] = []
    counts: ProposalCounts | None = None


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
    changeset_id = str(uuid.uuid4())
    try:
        identities = await roster_ingest.published_identities(jurisdiction_ocdid)
        roster, records_by_person = await roster_ingest.reconcile_roster(
            jurisdiction_ocdid,
            [row.sighting.model_dump() for row in rows],
            identities,
            taxonomy,
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
    changes = await _changes(changeset_id, jurisdiction_ocdid, records_by_person)
    if changes.counts is not None:
        await set_proposal_counts(changeset_id, changes.counts)
    return JurisdictionResult(
        jurisdiction_ocdid=jurisdiction_ocdid,
        status=ImportStatus.IMPORTED if error is None else ImportStatus.PARTIAL,
        changeset_id=changeset_id,
        people=len(roster),
        sightings=sightings,
        posts=posts,
        error=error,
        notes=changes.notes,
        published_other_names=changes.published_other_names,
        report=changes.report,
    )


async def _changes(
    changeset_id: str, jurisdiction_ocdid: str, records_by_person: dict[str, list[dict]]
) -> ImportChanges:
    """What this import changes: each row's note and published aliases, the report tab's rows,
    and the batch page's counts.

    Read through `proposed_roster`, so blank cells state nothing here either. Never fatal: the
    import already landed, and a missing note costs only the volunteer's feedback.
    """
    try:
        proposed = await proposed_roster(changeset_id, jurisdiction_ocdid)
        published_by_jurisdiction, proposals_by_changeset = await asyncio.gather(
            get_rosters_by_jurisdiction([jurisdiction_ocdid]),
            proposals_for_requests([changeset_id], {changeset_id: proposed}),
        )
        published = published_by_jurisdiction.get(jurisdiction_ocdid, [])
        proposals = proposals_by_changeset.get(changeset_id, [])
        diffs = person_diffs(published, proposed)
        likely_same = likely_same_people(published, proposed, diffs, proposals)
        notes = person_notes([person["id"] for person in proposed], diffs, proposals, likely_same)
        report = report_rows(
            jurisdiction_ocdid, published, proposed, diffs, proposals, likely_same
        )
        counts = proposal_counts(proposed, diffs, proposals)
    except Exception as e:
        logger.error(
            f"[{changeset_id}] {jurisdiction_ocdid}: notes failed: {e}", exc_info=True
        )
        return ImportChanges()
    return ImportChanges(
        notes=by_row(jurisdiction_ocdid, records_by_person, notes),
        published_other_names=by_row(
            jurisdiction_ocdid, records_by_person, published_other_names_by_person(published)
        ),
        report=report,
        counts=counts,
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


def read_rows(
    rows: list[dict], sites: SiteIndex, jurisdictions: JurisdictionIndex
) -> SheetRead:
    """Raw roster rows, parsed, with a preview of what importing them would do.

    Pure, and the only place that decides what "ready" and "blocked" mean. Both callers reach
    it: the one that opens the spreadsheet and the one that is handed rows over HTTP, so the two
    cannot come to different conclusions about the same rows.
    """
    parsed, errors = parse_rows(rows, sites, jurisdictions)

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
    form uses — and one of ours among the volunteer's reads as read-only, without anyone having
    to already know the contract. `lib.csv.column_key` strips both back off."""
    if column in REQUIRED_COLUMNS:
        return f"{column}{REQUIRED_MARKER}"
    if column == PUBLISHED_OTHER_NAMES:
        return f"{column}{READ_ONLY_MARKER}"
    return column


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


async def _site_index() -> SiteIndex:
    return build_site_index(await sites_db.site_owners())


async def _jurisdiction_index() -> JurisdictionIndex:
    return build_jurisdiction_index(await get_jurisdiction_geoids())


def _resolved_jurisdictions(
    roster: list[dict], sites: SiteIndex, jurisdictions: JurisdictionIndex
) -> set[str]:
    """Rows already handled never parse, so their town is resolved here instead.

    Through the same resolver the parse uses, not off the ocdid cell: nothing writes a resolved
    ocdid back into the sheet, so a row answered by its geoid or its site has a blank cell.
    """
    return {resolve_jurisdiction(row, sites, jurisdictions) for row in roster} - {""}


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
    return read_rows(roster_rows, await _site_index(), await _jurisdiction_index())


async def run_import(
    batch_id: str, rows: list[ImportRow], user_id: str
) -> None:
    """The background half: ingest, report back into the sheet, close the batch.

    `finish` releases the lock, so it must happen either way — including when the write-back
    fails, which must not hold the sheet against every future import.
    """
    status = changeset_batches.BatchStatus.SUCCEEDED
    error = None
    errors: list[RowError] = []
    try:
        results = await import_rows(rows, user_id, batch_id)
        # A jurisdiction failing is not an exception here — `_import_jurisdiction` catches its
        # own and reports it in the result — so without this the batch reads `succeeded` with
        # no hint that a town silently failed to import at all.
        errors = jurisdiction_errors(results)
        if any(result.status is ImportStatus.FAILED for result in results):
            status = changeset_batches.BatchStatus.FAILED
        await write_back(results)
        await import_report.write_report([row for result in results for row in result.report])
    except Exception as e:
        logger.error(f"[{batch_id}] import failed: {e}", exc_info=True)
        status, error = changeset_batches.BatchStatus.FAILED, str(e)
    await changeset_batches.finish(batch_id, status, error=error, errors=errors)


def jurisdiction_errors(results: list[JurisdictionResult]) -> list[RowError]:
    """A failed or partial jurisdiction as a batch error; it came from no one row."""
    return [
        RowError(
            line=None,
            jurisdiction_ocdid=result.jurisdiction_ocdid,
            column=None,
            message=result.error,
        )
        for result in results
        if result.error
    ]


async def write_back(results: list[JurisdictionResult]) -> None:
    """Stamp each roster row with what happened to it.

    The roster tab only. `Live[Jurisdictions]` is the sheet sync's to own — two writers on one
    tab raced, and with every state listed a per-town report described 9,464 rows to say
    something about twenty.

    Never fatal: the data is already ingested and waiting on the batch page, so a Sheets
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
        sites = await _site_index()
        jurisdictions = await _jurisdiction_index()
        parsed, errors = parse_rows(roster, sites, jurisdictions)

        by_ocdid = {result.jurisdiction_ocdid: result for result in results}
        imported = {
            ocdid
            for ocdid, result in by_ocdid.items()
            if result.status in (ImportStatus.IMPORTED, ImportStatus.PARTIAL)
        }
        notes = merge_jurisdiction_notes(
            {
                (result.jurisdiction_ocdid, name): note
                for result in results
                for name, note in result.notes.items()
            },
            parsed,
        )
        published_other_names = {
            (result.jurisdiction_ocdid, name): names
            for result in results
            for name, names in result.published_other_names.items()
        }
        dismissed = await dismissals.latest_import_dismissed(
            sorted(
                {row.jurisdiction_ocdid for row in parsed}
                | _resolved_jurisdictions(roster, sites, jurisdictions)
            )
        )
        await asyncio.to_thread(
            sheets.write_columns,
            spreadsheet_id,
            entry_sheet.ROSTER_TAB,
            roster_columns(
                roster,
                parsed,
                errors,
                imported,
                stamp,
                notes,
                published_other_names,
                dismissed,
            ),
        )
    except Exception as e:
        logger.error(f"Failed to write results back to the sheet: {e}", exc_info=True)
