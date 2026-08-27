"""The entry sheet's rows, both directions.

Rows in: a spreadsheet row becomes the sighting `source_records` stores. Columns out: what
happened to each row and each town, for the sheet's own `status` / `error` columns.

Pure either way — the Sheets calls are the caller's. Which sheet and which tabs is
`services.entry_sheet`. Spec: `.scratch/2026-08-25-sheet-import-shape.md`.

The sheet carries no ids — matching is ingest's job, so there is nowhere to paste a uuid wrong.
One row is one sighting; `roster_from_rows` groups by name, so two rows for one person would
invite "Bob Smith" and "Robert Smith" to become two people.
"""

import re

from pydantic import BaseModel

JURISDICTION = "jurisdiction_ocdid"
READY = "ready"

# Written by the import, never by a volunteer. Every row gets a value on every run: a row that
# failed last time and is fine now must not keep last time's message.
STATUS_COLUMNS = ("status", "error", "last_import_at")

# What `status` can say.
IMPORTED = "imported"
ERROR = "error"
SKIPPED = "skipped"
BLOCKED = "blocked"

_OPTIONAL = ("url", "phone", "email", "image", "start_date", "end_date")
_REQUIRED = (JURISDICTION, "name", "label")

# Partial dates allowed: `source_records.start_date` is text for that reason.
_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

_TRUTHY = frozenset({"true", "yes", "y", "1", "x", "✓"})
_FALSEY = frozenset({"false", "no", "n", "0", ""})


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


def _clean(value) -> str:
    return "" if value is None else str(value).strip()


def _optional(value) -> str | None:
    return _clean(value) or None


def _boolean(value) -> bool | None:
    text = _clean(value).lower()
    if text in _TRUTHY:
        return True
    return False if text in _FALSEY else None


def parse_rows(
    rows: list[dict], source_url: str
) -> tuple[list[ImportRow], list[RowError]]:
    """Every row that parsed, and every reason one did not.

    `source_url` is the sheet, not a cell — Sheets gives a row no durable url of its own. Line
    numbers count the header, so they match the row gutter a volunteer sees.
    """
    parsed: list[ImportRow] = []
    errors: list[RowError] = []

    for offset, row in enumerate(rows):
        line = offset + 2
        row_errors = _row_errors(row, line)
        if row_errors:
            errors.extend(row_errors)
        else:
            parsed.append(_import_row(row, line, source_url))

    return parsed, errors + _duplicate_errors(parsed)


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
    errors.extend(
        _error(row, line, column, f"not YYYY, YYYY-MM or YYYY-MM-DD: {value!r}")
        for column in ("start_date", "end_date")
        if (value := _clean(row.get(column))) and not _DATE.match(value)
    )
    return errors


def _import_row(row: dict, line: int, source_url: str) -> ImportRow:
    return ImportRow(
        line=line,
        jurisdiction_ocdid=_clean(row[JURISDICTION]),
        sighting=Sighting(
            name=_clean(row["name"]),
            label=_clean(row["label"]),
            source_url=source_url,
            **{column: _optional(row.get(column)) for column in _OPTIONAL},
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


def rows_by_jurisdiction(rows: list[ImportRow]) -> dict[str, list[ImportRow]]:
    grouped: dict[str, list[ImportRow]] = {}
    for row in rows:
        grouped.setdefault(row.jurisdiction_ocdid, []).append(row)
    return grouped


def ready_jurisdictions(ready_rows: list[dict]) -> set[str]:
    """The towns a volunteer marked finished, from `Entry · Jurisdictions`.

    Only they know a town is done; the maintainer running the import cannot.
    """
    return {
        _clean(row[JURISDICTION])
        for row in ready_rows
        if _clean(row.get(JURISDICTION)) and _boolean(row.get(READY))
    }


# ── Columns out ──────────────────────────────────────────────────────────────


def roster_columns(
    rows: list[ImportRow],
    errors: list[RowError],
    row_count: int,
    imported: set[str],
    skipped: set[str],
    stamp: str,
) -> dict[str, list]:
    """`status`, `error` and `last_import_at` for every row of the roster tab.

    Every row, not only the ones that changed: a row that failed last run and is fine now needs
    its error cleared, and leaving it would have the volunteer chasing a problem they fixed.

    A row is `blocked` when its own jurisdiction was rejected over somebody else's bad row —
    which is most of a blocked town, and the reason has to point elsewhere or it reads as a
    fault in a row that is perfectly fine.
    """
    error_by_line = {error.line: error for error in errors}
    jurisdiction_by_line = {row.line: row.jurisdiction_ocdid for row in rows}
    blocked = {error.jurisdiction_ocdid for error in errors}

    status, message = [], []
    for line in range(2, row_count + 2):
        error = error_by_line.get(line)
        jurisdiction = jurisdiction_by_line.get(line) or (
            error.jurisdiction_ocdid if error else ""
        )
        if error:
            status.append(ERROR)
            message.append(f"{error.column}: {error.message}" if error.column else error.message)
        elif jurisdiction in imported:
            status.append(IMPORTED)
            message.append("")
        elif jurisdiction in skipped:
            status.append(SKIPPED)
            message.append("not marked ready")
        elif jurisdiction in blocked:
            status.append(BLOCKED)
            message.append("another row in this town was rejected")
        else:
            status.append("")
            message.append("")

    return {
        "status": status,
        "error": message,
        "last_import_at": [stamp] * len(status),
    }


def jurisdiction_columns(
    ocdids: list[str],
    counts: dict[str, int],
    results: dict[str, tuple[str, str | None]],
    stamp: str,
) -> dict[str, list]:
    """`rows`, `status`, `error` and `last_import_at` for the worklist tab, in its own order.

    Keyed by the ocdid the volunteer picked rather than by position, so re-sorting their tab
    between runs cannot write Sherborn's outcome onto Concord's row.
    """
    status, message = [], []
    for ocdid in ocdids:
        disposition, error = results.get(ocdid, ("", None))
        status.append(disposition)
        message.append(error or "")

    return {
        "rows": [counts.get(ocdid, 0) for ocdid in ocdids],
        "status": status,
        "error": message,
        "last_import_at": [stamp] * len(ocdids),
    }
