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


_REQUIRED = (JURISDICTION, "name", "source_url")
_OPTIONAL = ("email", "phone", "image", "label")


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


def parse_rows(rows: list[dict]) -> tuple[list[ImportRow], list[RowError]]:
    """Every row that parsed, and every reason one did not.

    Line numbers count the header, so they match the row gutter a volunteer sees.
    """
    parsed: list[ImportRow] = []
    errors: list[RowError] = []

    for offset, row in enumerate(rows):
        line = offset + 2
        # A row with nothing in it is grid, not a row somebody wrote. Sheets returns every line
        # in the used range, so a tab with 4 entries and 140 spare lines otherwise reports 420
        # "required" errors and blocks the import on rows nobody typed.
        if _is_blank(row):
            continue
        row_errors = _row_errors(row, line)
        if row_errors:
            errors.extend(row_errors)
        else:
            parsed.append(_import_row(row, line))

    return parsed, errors + _duplicate_errors(parsed)


# What a volunteer fills in. `STATUS_COLUMNS` are ours and deliberately excluded below.
_VOLUNTEER_COLUMNS = _REQUIRED + _OPTIONAL

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


def _import_row(row: dict, line: int) -> ImportRow:
    return ImportRow(
        line=line,
        jurisdiction_ocdid=_clean(row[JURISDICTION]),
        status=_clean(row.get("status")),
        sighting=Sighting(
            name=_clean(row["name"]),
            label=_clean(row.get("label")),
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
    rows: list[ImportRow],
    errors: list[RowError],
    row_count: int,
    imported: set[str],
    stamp: str,
) -> dict[str, list]:
    """`status`, `error` and `last_import_at` for every row of the roster tab.

    Every row, not only the ones that changed: a row that failed last run and is fine now needs
    its error cleared, and leaving it would have the volunteer chasing a problem they fixed.

    A row is `blocked` when its own jurisdiction was rejected over somebody else's bad row —
    which is most of a blocked town, and the reason has to point elsewhere or it reads as a
    fault in a row that is perfectly fine.

    **A row this run did not touch keeps what it already said.** Blanking it would erase the
    very thing the next run reads to decide it has already been handled — which is a loop: the
    skip blanks the status, the blank asks for a re-import, the re-import writes it back.
    """
    previous = {row.line: row.status for row in rows}
    error_by_line = {error.line: error for error in errors}
    jurisdiction_by_line = {row.line: row.jurisdiction_ocdid for row in rows}
    blocked = {error.jurisdiction_ocdid for error in errors}

    # A line the parse produced nothing for is a spare line. Stamping it writes app data into
    # a row nobody used, and the next run then reads that row as occupied.
    written = set(previous) | set(error_by_line)

    status, message, stamps = [], [], []
    for line in range(2, row_count + 2):
        stamps.append(stamp if line in written else "")
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
            # Untouched this run — a skipped locality, or a row the parse never reached.
            status.append(previous.get(line, ""))
            message.append("")

    return {
        "status": status,
        "error": message,
        "last_import_at": stamps,
    }
