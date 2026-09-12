"""The entry sheet's rows, both directions.

Rows in: a spreadsheet row becomes the sighting `source_records` stores. Columns out: what
happened to each row and each town, for the sheet's own `status` / `error` columns.

Pure either way — the Sheets calls are the caller's. Which sheet and which tabs is
`services.entry_sheet`. Spec: `.scratch/2026-08-25-sheet-import-shape.md`.

The sheet carries no ids — matching is ingest's job, so there is nowhere to paste a uuid wrong.
One row is one sighting; `roster_from_rows` groups by name, so two rows for one person would
invite "Bob Smith" and "Robert Smith" to become two people.

`jurisdiction_ocdid` is typed or pasted directly — never a geoid. A geoid needs a database read
to resolve, which makes it exact but also a guess-and-check step for anything that does not
already have one; an ocdid a source cannot spell correctly fails the same way a typo always
did, at import, per jurisdiction, same as a hand-typed one always has.
"""

from enum import StrEnum

from pydantic import BaseModel
from shared.utils.email_utils import is_valid_email
from shared.utils.phone_utils import normalize_phone_number
from shared.utils.url_utils import is_web_url

JURISDICTION = "jurisdiction_ocdid"

# Written by the import, never by a volunteer. Every row gets a value on every run: a row that
# failed last time and is fine now must not keep last time's message.
STATUS_COLUMNS = ("status", "error", "last_import_at")

# What a row's `status` can say.
IMPORTED = "imported"
ERROR = "error"
BLOCKED = "blocked"


class ImportStatus(StrEnum):
    """What a whole jurisdiction's `status` can say. Coarser than a row's: a town is the unit
    that succeeds or fails, because a town is the unit that gets imported."""

    IMPORTED = "imported"
    # People stored, posts not. Re-derivable from the sightings, so not a failure.
    PARTIAL = "partial"
    FAILED = "failed"
    # The sheet says exactly what it said last run, so no card was raised.
    UNCHANGED = "unchanged"


_REQUIRED = (JURISDICTION, "name", "source_url", "label")
_OPTIONAL = ("email", "phone", "image")

# `label` is required so a blank cell is a caught mistake, not silent — a source with no title
# says so deliberately, with `inherit`, rather than leaving the cell empty.
#
# Cannot be resolved here — it needs the person's current open membership, a database read.
# `services.sheet_import` looks it up by name and substitutes the real label text before
# parsing continues, so everything downstream sees this exactly as if the source had sent it.
# A name holding nothing open degrades to blank — the same shape a blank cell would be, if
# blank were still allowed — so there is no separate "no title at all" sentinel to also support.
INHERIT = "inherit"


class RowError(BaseModel):
    """A problem with one row, as data — reported, never raised.

    Carries its jurisdiction because a rejected row never becomes an `ImportRow`, and the
    importer blocks per jurisdiction: without this there is nothing to attribute it to.
    """

    line: int
    jurisdiction_ocdid: str
    column: str | None
    message: str


class Sighting(BaseModel):
    """Exactly what `insert_source_records` writes, keyed as `source_records` names it."""

    name: str
    label: str
    source_url: str
    url: str | None = None
    phone: str | None = None
    email: str | None = None
    image: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ImportRow(BaseModel):
    line: int
    jurisdiction_ocdid: str
    sighting: Sighting
    # What the last run wrote here. Blank for a row nobody has imported, and blank again when a
    # volunteer clears it to say "look at this one again".
    status: str = ""


def _clean(value) -> str:
    return "" if value is None else str(value).strip()


def _optional(value) -> str | None:
    return _clean(value) or None


def _handled_jurisdictions(rows: list[dict]) -> set[str]:
    """Every jurisdiction whose rows all already carry a status — on the raw, unvalidated
    jurisdiction cell, since this runs before a row is known to parse at all.

    Whole, not row by row: a town where every row already says `imported` is genuinely
    unchanged, but a town with one cleared row among ten `imported` ones is not — clearing one
    row is how a volunteer asks for the whole town again (`ImportRow`-level `already_handled`
    documents the same rule downstream, on rows that did parse).
    """
    by_jurisdiction: dict[str, list[dict]] = {}
    for row in rows:
        if _is_blank(row):
            continue
        by_jurisdiction.setdefault(_clean(row.get(JURISDICTION)), []).append(row)
    return {
        jurisdiction
        for jurisdiction, jurisdiction_rows in by_jurisdiction.items()
        if all(_clean(row.get("status")) for row in jurisdiction_rows)
    }


def parse_rows(rows: list[dict]) -> tuple[list[ImportRow], list[RowError]]:
    """Every row that parsed, and every reason one did not.

    Line numbers count the header, so they match the row gutter a volunteer sees.
    """
    parsed: list[ImportRow] = []
    errors: list[RowError] = []

    handled = _handled_jurisdictions(rows)
    for offset, row in enumerate(rows):
        line = offset + 2
        # A row with nothing in it is grid, not a row somebody wrote. Sheets returns every line
        # in the used range, so a tab with 4 entries and 140 spare lines otherwise reports 420
        # "required" errors and blocks the import on rows nobody typed.
        if _is_blank(row):
            continue
        # Already handled — clearing a row's status is how a volunteer asks for it again, and
        # doing that on any one row brings the whole town back (see `_handled_jurisdictions`).
        # Skipped before validation, not just before import: a row that fails validation never
        # becomes an `ImportRow`, so the existing jurisdiction-level "all handled" check
        # (`already_handled`, in `services.sheet_import`) never even sees it — and a contract
        # change made after the row was accepted (a new required column, say) would otherwise
        # re-reject a row nothing is wrong with, forever, on every run.
        if _clean(row.get(JURISDICTION)) in handled:
            continue
        row_errors = _row_errors(row, line)
        if row_errors:
            errors.extend(row_errors)
        else:
            parsed.append(_import_row(row, line))

    return parsed, errors + _duplicate_errors(parsed)


# What a volunteer fills in. `STATUS_COLUMNS` are ours and deliberately excluded below.
_VOLUNTEER_COLUMNS = _REQUIRED + _OPTIONAL

# Public: `services.sheet_import` marks these on the sheet itself, so a required column reads
# as required without anyone having to already know the contract.
REQUIRED_COLUMNS = _REQUIRED

# The header row in full — the single source of truth `services.sheet_import` writes to the
# sheet itself, so the contract can never drift from what this module actually reads.
ROSTER_HEADERS = _REQUIRED + _OPTIONAL + STATUS_COLUMNS


def _is_blank(row: dict) -> bool:
    """Whether the volunteer typed anything on this line.

    App-owned columns do not count. The write-back used to stamp `last_import_at` down the whole
    used range, so a spare line can carry a timestamp and still be a line nobody wrote — judging
    on every value would call it occupied and reject it three times over.
    """
    return not any(_clean(row.get(column)) for column in _VOLUNTEER_COLUMNS)


def _error(row: dict, line: int, column: str | None, message: str) -> RowError:
    return RowError(
        line=line,
        jurisdiction_ocdid=_clean(row.get(JURISDICTION)),
        column=column,
        message=message,
    )


def _row_errors(row: dict, line: int) -> list[RowError]:
    errors = [
        _error(row, line, column, "required")
        for column in _REQUIRED
        if not _clean(row.get(column))
    ]
    # The same checks `SubmittedPersonRecord` applies, run here so a bad cell is a rejected row
    # the volunteer sees in the sheet rather than a record that fails further down.
    for column, ok, expected in (
        ("phone", lambda v: normalize_phone_number(v) is not None, "not a phone number"),
        ("email", is_valid_email, "not an email address"),
        ("source_url", is_web_url, "not an http(s) url with a domain"),
    ):
        value = _clean(row.get(column))
        if value and not ok(value):
            errors.append(_error(row, line, column, f"{expected}: {value!r}"))
    return errors


def _label(value: str) -> str:
    """`inherit` passes through verbatim; resolving it is `services.sheet_import`'s job."""
    return INHERIT if value.lower() == INHERIT else value


def _import_row(row: dict, line: int) -> ImportRow:
    return ImportRow(
        line=line,
        jurisdiction_ocdid=_clean(row[JURISDICTION]),
        status=_clean(row.get("status")),
        sighting=Sighting(
            name=_clean(row["name"]),
            label=_label(_clean(row["label"])),
            source_url=_clean(row["source_url"]),
            email=_optional(row.get("email")),
            phone=_optional(row.get("phone")),
            image=_optional(row.get("image")),
        ),
    )


def _duplicate_errors(rows: list[ImportRow]) -> list[RowError]:
    """`memberships` allows one open row per (person, organization) and a jurisdiction has one
    organization, so two rows for one person is unrepresentable."""
    seen: dict[tuple, int] = {}
    errors = []
    for row in rows:
        key = (row.jurisdiction_ocdid, row.sighting.name.lower())
        if key in seen:
            errors.append(
                RowError(
                    line=row.line,
                    jurisdiction_ocdid=row.jurisdiction_ocdid,
                    column="name",
                    message=f"already on line {seen[key]} for this jurisdiction",
                )
            )
        else:
            seen[key] = row.line
    return errors


def already_handled(rows: list[ImportRow]) -> bool:
    return all(row.status for row in rows)


def rows_by_jurisdiction(rows: list[ImportRow]) -> dict[str, list[ImportRow]]:
    grouped: dict[str, list[ImportRow]] = {}
    for row in rows:
        grouped.setdefault(row.jurisdiction_ocdid, []).append(row)
    return grouped


# ── Columns out ──────────────────────────────────────────────────────────────


def roster_columns(
    raw_rows: list[dict],
    rows: list[ImportRow],
    errors: list[RowError],
    imported: set[str],
    stamp: str,
) -> dict[str, list]:
    """`status`, `error` and `last_import_at` for every row of the roster tab.

    Every row, not only the ones that changed: a row that failed last run and is fine now needs
    its error cleared, and leaving it would have the volunteer chasing a problem they fixed.

    A row is `blocked` when its own jurisdiction was rejected over somebody else's bad row —
    which is most of a blocked town, and the reason has to point elsewhere or it reads as a
    fault in a row that is perfectly fine.

    **A row this run did not touch keeps what it already said — status *and* timestamp.**
    `raw_rows` is the fallback source for both, not `rows`: an already-handled jurisdiction is
    now skipped before parsing even runs (`_handled_jurisdictions`), so its rows never become
    `ImportRow`s at all, and reading "what it already said" from the parse would just find
    nothing — the same as a blank cell — and blank it. Reading the sheet's own current cells
    instead is what keeps status and timestamp from decaying to blank purely because a
    jurisdiction was skipped, not because a volunteer cleared anything.
    """
    previous_status = {offset + 2: _clean(row.get("status")) for offset, row in enumerate(raw_rows)}
    previous_stamp = {
        offset + 2: _clean(row.get("last_import_at")) for offset, row in enumerate(raw_rows)
    }
    error_by_line = {error.line: error for error in errors}
    jurisdiction_by_line = {row.line: row.jurisdiction_ocdid for row in rows}
    blocked = {error.jurisdiction_ocdid for error in errors}

    # Only a line the parse actually reached this run — imported, blocked, or rejected — gets a
    # fresh stamp. Anything else (a spare line, or a row skipped as already handled) keeps
    # whatever timestamp the sheet already had, same as its status.
    written = {row.line for row in rows} | set(error_by_line)

    status, message, stamps = [], [], []
    for line in range(2, len(raw_rows) + 2):
        stamps.append(stamp if line in written else previous_stamp.get(line, ""))
        error = error_by_line.get(line)
        jurisdiction = jurisdiction_by_line.get(line) or (
            error.jurisdiction_ocdid if error else ""
        )
        if error:
            status.append(ERROR)
            message.append(
                f"{error.column}: {error.message}" if error.column else error.message
            )
        elif jurisdiction in imported:
            status.append(IMPORTED)
            message.append("")
        elif jurisdiction in blocked:
            status.append(BLOCKED)
            message.append("another row in this town was rejected")
        else:
            # Untouched this run — a skipped locality, a row the parse never reached, or a
            # spare line.
            status.append(previous_status.get(line, ""))
            message.append("")

    return {
        "status": status,
        "error": message,
        "last_import_at": stamps,
    }
