"""The `Live[Import][...]` tab: what one sheet import proposes, one person per row.

Pure. Built from the same diffs as the roster tab's `note` column, so the two cannot disagree.
Each row is the person as the import would leave them; a changed cell is tinted and carries what
it said before in its note, the way comparison tools show a record diff.
"""

from datetime import datetime

from pydantic import BaseModel

from core.roster_changes import ChangeKind, PersonChange
from schemas.sheets import SheetCell

REPORT_TAB_PREFIX = "Live[Import]"
REPORT_TABS_KEPT = 5

POST_FIELD = "post"
NAME_FIELD = "name"
# The person's own fields, in the review card's order; the post sits beside the name.
PERSON_FIELDS = ["other_names", "emails", "phones", "urls", "start_date", "end_date"]
REPORT_HEADERS = ["jurisdiction_ocdid", "change", NAME_FIELD, POST_FIELD, *PERSON_FIELDS]


def _rgb(hex_color: str) -> dict[str, float]:
    return {
        channel: int(hex_color[index : index + 2], 16) / 255
        for channel, index in (("red", 1), ("green", 3), ("blue", 5))
    }


# The review page's hues: a new person's row green, a departing one's red, a changed cell amber.
ADDED_ROW = _rgb("#e6f4ea")
ABSENT_ROW = _rgb("#fce8e6")
CHANGED_CELL = _rgb("#fef7e0")


class ReportCell(BaseModel):
    value: str
    # Set when the import changes this cell: what it said before ("" for nothing).
    before: str | None = None
    note: str | None = None


class ImportReportRow(BaseModel):
    jurisdiction_ocdid: str
    change: ChangeKind
    cells: dict[str, ReportCell]


def report_tab(now: datetime) -> str:
    # The zone in the name: the batch page shows local time. The format sorts as text.
    return f"{REPORT_TAB_PREFIX}[{now.strftime('%Y-%m-%d %H:%M')} UTC]"


def report_tabs_in_order(titles: list[str]) -> list[str]:
    """Newest first, so the latest import sits right beside the entry tab."""
    return sorted(
        (title for title in titles if title.startswith(REPORT_TAB_PREFIX)), reverse=True
    )


def stale_report_tabs(titles: list[str], new_tab: str) -> list[str]:
    """Report tabs to delete before writing `new_tab`, so it and the newest others make
    `REPORT_TABS_KEPT`. A same-minute tab goes too: rewriting it would leave its longer tail."""
    reports = [title for title in report_tabs_in_order(titles) if title != new_tab]
    return ([new_tab] if new_tab in titles else []) + reports[REPORT_TABS_KEPT - 1 :]


def _text(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return "" if value is None else str(value)


def _post_labels(record: dict) -> str:
    return ", ".join(
        membership["post_label"] for membership in record.get("memberships") or []
    )


def _post_cell(change: PersonChange, published: dict, proposed: dict | None) -> ReportCell:
    """What they hold now, and — when an office moved, was created or was left — what they held
    before. Both read off the rows, so the cell says what the roster says."""
    value = _post_labels(proposed or {})
    if not change.offices:
        return ReportCell(value=value)
    return ReportCell(value=value, before=_post_labels(published))


def _person_row(
    jurisdiction_ocdid: str,
    published: dict,
    proposed: dict | None,
    change: PersonChange,
    likely_same_as: str | None,
) -> ImportReportRow:
    # An absent person is only in the published roster, and is shown as they last were.
    record = proposed or published
    changed = set(change.fields)
    cells = {
        field: ReportCell(
            value=_text(record.get(field)),
            before=_text(published.get(field)) if field in changed else None,
        )
        for field in [NAME_FIELD, *PERSON_FIELDS]
    }
    if likely_same_as:
        cells[NAME_FIELD].note = f"may be {likely_same_as}"
    cells[POST_FIELD] = _post_cell(change, published, proposed)
    return ImportReportRow(
        jurisdiction_ocdid=jurisdiction_ocdid, change=change.kind, cells=cells
    )


def report_rows(
    jurisdiction_ocdid: str,
    published: list[dict],
    proposed: list[dict],
    changes: list[PersonChange],
    likely_same: dict[str, str],
) -> list[ImportReportRow]:
    """One row per person the import changes: added, edited, moved, given a post, or absent."""
    published_by_id = {person["id"]: person for person in published}
    proposed_by_id = {person["id"]: person for person in proposed}
    rows = [
        _person_row(
            jurisdiction_ocdid,
            published_by_id.get(change.person_id, {}),
            proposed_by_id.get(change.person_id),
            change,
            likely_same.get(change.person_id),
        )
        for change in changes
        if change.kind is not ChangeKind.UNCHANGED
    ]
    return sorted(rows, key=lambda row: row.cells[NAME_FIELD].value)


def _sheet_cell(cell: ReportCell, row_background: dict[str, float] | None) -> SheetCell:
    if row_background is not None or cell.before is None:
        return SheetCell(value=cell.value, background=row_background, note=cell.note)
    return SheetCell(
        value=cell.value, background=CHANGED_CELL, note=f"was: {cell.before or '(none)'}"
    )


def row_cells(row: ImportReportRow) -> list[SheetCell]:
    """An added row is new throughout and an absent one leaves whole, so both are tinted as a
    row; otherwise only the changed cells are, each noting what it said before."""
    row_background = None
    if row.change is ChangeKind.ADDED:
        row_background = ADDED_ROW
    elif row.change is ChangeKind.ABSENT:
        row_background = ABSENT_ROW
    return [
        SheetCell(value=row.jurisdiction_ocdid, background=row_background),
        SheetCell(value=row.change.value, background=row_background),
        *(_sheet_cell(row.cells[field], row_background) for field in REPORT_HEADERS[2:]),
    ]
