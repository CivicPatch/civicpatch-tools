"""The import sheet's columns out: what happened to each row and town, written back into the
app-owned columns (`STATUS_COLUMNS`) and a jurisdiction the row's source site resolved.

Pure: the Sheets calls are the caller's. Rows in is `sheet_import_rows`.
"""

from core.sheet_import_rows import JURISDICTION, ImportRow, RowError, clean_cell, row_key

# What a row's `status` can say.
IMPORTED = "imported"
ERROR = "error"
BLOCKED = "blocked"


def _jurisdiction_column(raw_rows: list[dict], rows: list[ImportRow]) -> list[str]:
    """The volunteer's own cell, verbatim, or the jurisdiction a blank one resolved to — so they
    see what their row was matched to, and the next read keys on it."""
    resolved = {row.line: row.jurisdiction_ocdid for row in rows}
    return [
        str(row.get(JURISDICTION) or "") or resolved.get(offset + 2, "")
        for offset, row in enumerate(raw_rows)
    ]


def _note_column(
    raw_rows: list[dict],
    jurisdictions: list[str],
    imported: set[str],
    notes: dict[tuple[str, str], str],
    dismissed: set[str],
) -> list[str]:
    """A town imported this run gets fresh notes. Otherwise the note stays until the town's
    last import is dismissed, when it no longer describes anything that can happen."""
    column = []
    for row, jurisdiction_cell in zip(raw_rows, jurisdictions):
        key = row_key(jurisdiction_cell, row.get("name") or "")
        jurisdiction = key[0]
        if jurisdiction in imported:
            column.append(notes.get(key, ""))
        elif jurisdiction in dismissed:
            column.append("")
        else:
            column.append(clean_cell(row.get("note")))
    return column


def roster_columns(
    raw_rows: list[dict],
    rows: list[ImportRow],
    errors: list[RowError],
    imported: set[str],
    stamp: str,
    notes: dict[tuple[str, str], str],
    dismissed: set[str],
) -> dict[str, list]:
    """`status`, `error`, `last_import_at` and `note` for every row of the roster tab, and
    `jurisdiction_ocdid` filled in where the row's source site resolved a blank one.

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
    previous_status = {offset + 2: clean_cell(row.get("status")) for offset, row in enumerate(raw_rows)}
    previous_stamp = {
        offset + 2: clean_cell(row.get("last_import_at")) for offset, row in enumerate(raw_rows)
    }
    error_by_line = {error.line: error for error in errors}
    jurisdiction_by_line = {row.line: row.jurisdiction_ocdid for row in rows}
    # Not blank: a row whose site resolved nothing has no town to block.
    blocked = {error.jurisdiction_ocdid for error in errors} - {""}

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

    jurisdictions = _jurisdiction_column(raw_rows, rows)
    return {
        JURISDICTION: jurisdictions,
        "status": status,
        "error": message,
        "last_import_at": stamps,
        "note": _note_column(raw_rows, jurisdictions, imported, notes, dismissed),
    }
