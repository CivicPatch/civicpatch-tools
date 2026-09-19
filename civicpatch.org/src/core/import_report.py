"""The `Live[Import][...]` tab: what one sheet import proposes, one person per row.

Pure. Built from the same diffs as the roster tab's `note` column, so the two cannot disagree.
Each row is the person as the import would leave them; a changed cell is tinted and carries what
it said before in its note, the way comparison tools show a record diff.
"""

from datetime import datetime

from pydantic import BaseModel

from core.membership_proposal import MembershipDisposition, ProposedChange
from core.roster_diff import DiffType, PersonDiff
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


class ImportReportRow(BaseModel):
    jurisdiction_ocdid: str
    # The headline: added, else absent, else the post's move or new post, else changed.
    change: DiffType | MembershipDisposition
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


def _headline(
    diff: PersonDiff | None, proposals: list[ProposedChange]
) -> DiffType | MembershipDisposition:
    if diff is not None and diff.type is DiffType.ADDED:
        return DiffType.ADDED
    dispositions = {proposal.disposition for proposal in proposals}
    for disposition in (
        MembershipDisposition.ABSENT,
        MembershipDisposition.MOVED,
        MembershipDisposition.NEW,
    ):
        if disposition in dispositions:
            return disposition
    return DiffType.CHANGED


def _post_cell(proposals: list[ProposedChange]) -> ReportCell:
    held = [p for p in proposals if p.disposition is not MembershipDisposition.ABSENT]
    value = ", ".join(proposal.post.label for proposal in held)
    moved = [p for p in proposals if p.disposition is not MembershipDisposition.UNCHANGED]
    if not moved:
        return ReportCell(value=value)
    before = [
        (proposal.from_post or proposal.post).label
        for proposal in proposals
        if proposal.disposition is not MembershipDisposition.NEW
    ]
    return ReportCell(value=value, before=", ".join(before))


def _person_row(
    jurisdiction_ocdid: str,
    published: dict,
    proposed: dict | None,
    diff: PersonDiff | None,
    proposals: list[ProposedChange],
) -> ImportReportRow:
    # An absent person is only in the published roster, and is shown as they last were.
    record = proposed or published
    changed = set(diff.fields) if diff is not None else set()
    cells = {
        field: ReportCell(
            value=_text(record.get(field)),
            before=_text(published.get(field)) if field in changed else None,
        )
        for field in [NAME_FIELD, *PERSON_FIELDS]
    }
    cells[POST_FIELD] = _post_cell(proposals)
    return ImportReportRow(
        jurisdiction_ocdid=jurisdiction_ocdid, change=_headline(diff, proposals), cells=cells
    )


def report_rows(
    jurisdiction_ocdid: str,
    published: list[dict],
    proposed: list[dict],
    diffs: list[PersonDiff],
    proposals: list[ProposedChange],
) -> list[ImportReportRow]:
    """One row per person the import changes: added, edited, moved, given a post, or absent."""
    published_by_id = {person["id"]: person for person in published}
    proposed_by_id = {person["id"]: person for person in proposed}
    diff_by_id = {diff.person_id: diff for diff in diffs}
    proposals_by_id: dict[str, list[ProposedChange]] = {}
    for proposal in proposals:
        proposals_by_id.setdefault(proposal.person_id, []).append(proposal)
    touched = list(
        dict.fromkeys(
            [diff.person_id for diff in diffs]
            + [
                proposal.person_id
                for proposal in proposals
                if proposal.disposition is not MembershipDisposition.UNCHANGED
            ]
        )
    )
    rows = [
        _person_row(
            jurisdiction_ocdid,
            published_by_id.get(person_id, {}),
            proposed_by_id.get(person_id),
            diff_by_id.get(person_id),
            proposals_by_id.get(person_id, []),
        )
        for person_id in touched
    ]
    return sorted(rows, key=lambda row: row.cells[NAME_FIELD].value)


def _sheet_cell(cell: ReportCell, row_background: dict[str, float] | None) -> SheetCell:
    if row_background is not None or cell.before is None:
        return SheetCell(value=cell.value, background=row_background)
    return SheetCell(
        value=cell.value, background=CHANGED_CELL, note=f"was: {cell.before or '(none)'}"
    )


def row_cells(row: ImportReportRow) -> list[SheetCell]:
    """An added row is new throughout and an absent one leaves whole, so both are tinted as a
    row; otherwise only the changed cells are, each noting what it said before."""
    row_background = None
    if row.change is DiffType.ADDED:
        row_background = ADDED_ROW
    elif row.change is MembershipDisposition.ABSENT:
        row_background = ABSENT_ROW
    return [
        SheetCell(value=row.jurisdiction_ocdid, background=row_background),
        SheetCell(value=row.change.value, background=row_background),
        *(_sheet_cell(row.cells[field], row_background) for field in REPORT_HEADERS[2:]),
    ]
