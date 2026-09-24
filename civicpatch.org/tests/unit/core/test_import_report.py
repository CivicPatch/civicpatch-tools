"""The import report tab: one row per change, and which old report tabs to drop. Pure.

The fixtures moved on 2026-09-24: a row used to be built from a person diff plus hand-written
`ProposedChange`s, and is now built from the two card sides `changes_of` reads. Every test's
claim is unchanged — an office is stated as a membership on a row rather than as a proposal
about one, because that is where the fold puts it.
"""

from datetime import datetime, timezone

import pytest

from core.import_report import (
    ABSENT_ROW,
    ADDED_ROW,
    CHANGED_CELL,
    REPORT_HEADERS,
    REPORT_TABS_KEPT,
    report_rows,
    report_tab,
    report_tabs_in_order,
    row_cells,
    stale_report_tabs,
)
from core.roster_changes import changes_of
from schemas.sheets import SheetCell

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government"
_DIVISION = "ocd-division/country:us/state:ma/county:middlesex/place:sherborn"


def _office(label: str) -> dict:
    return {"organization_id": "org", "post_id": f"post-{label}", "post_label": label}


def _rows(published: list[dict], proposed: list[dict], likely_same: dict | None = None):
    return report_rows(
        _OCDID, published, proposed, changes_of(published, proposed), likely_same or {}
    )


def _cells(row) -> dict[str, SheetCell]:
    return dict(zip(REPORT_HEADERS, row_cells(row)))


def test_a_changed_field_shows_the_new_value_tinted_with_the_old_in_its_note():
    published = [{"id": "p1", "name": "Ana Reyes", "emails": ["ana@old.gov"]}]
    proposed = [{"id": "p1", "name": "Ana Reyes", "emails": ["ana@new.gov"]}]

    [row] = _rows(published, proposed, [])
    cells = _cells(row)

    assert cells["change"].value == "changed"
    assert cells["emails"] == SheetCell(
        value="ana@new.gov", background=CHANGED_CELL, note="was: ana@old.gov"
    )
    assert cells["name"] == SheetCell(value="Ana Reyes")


def test_a_new_person_is_one_green_row_with_their_post():
    proposed = [
        {"id": "p2", "name": "Ben Ortiz", "memberships": [_office("Select Board Member")]}
    ]

    [row] = _rows([], proposed)
    cells = _cells(row)

    assert cells["change"].value == "added"
    assert cells["post"].value == "Select Board Member"
    assert all(cell.background == ADDED_ROW for cell in cells.values())


def test_a_move_notes_the_post_left_and_an_absence_keeps_the_last_published_values():
    """An absent person is only in the published roster, so their row comes from there."""
    published = [
        {"id": "p1", "name": "Ana Reyes", "memberships": [_office("Member")]},
        {
            "id": "p3",
            "name": "Cal Diaz",
            "emails": ["cal@town.gov"],
            "memberships": [_office("Clerk")],
        },
    ]
    proposed = [{"id": "p1", "name": "Ana Reyes", "memberships": [_office("Chair")]}]

    ana, cal = [_cells(row) for row in _rows(published, proposed)]

    assert ana["change"].value == "moved"
    assert ana["post"] == SheetCell(value="Chair", background=CHANGED_CELL, note="was: Member")
    assert cal["change"].value == "absent"
    assert cal["emails"] == SheetCell(value="cal@town.gov", background=ABSENT_ROW)


def test_an_unchanged_membership_is_not_reported():
    proposed = [{"id": "p1", "name": "Ana Reyes", "memberships": [_office("Chair")]}]

    assert _rows(proposed, proposed) == []


def test_the_tab_name_carries_its_minute_in_utc():
    stamp = datetime(2026, 9, 18, 21, 47, tzinfo=timezone.utc)

    assert report_tab(stamp) == "Live[Import][2026-09-18 21:47 UTC]"


def _report(day: int) -> str:
    return report_tab(datetime(2026, 9, day, 12, 0, tzinfo=timezone.utc))


def test_report_tabs_sort_newest_first_and_ignore_the_rest():
    titles = ["Entry[Roster]", _report(10), "Live[People][MA]", _report(12), _report(11)]

    assert report_tabs_in_order(titles) == [_report(12), _report(11), _report(10)]


def test_writing_a_report_drops_all_but_the_newest_others():
    """The new one plus the newest four makes five."""
    older = [_report(day) for day in range(1, 8)]

    stale = stale_report_tabs(["Entry[Roster]", *older], _report(20))

    assert stale == [_report(day) for day in (3, 2, 1)]
    assert len(older) - len(stale) == REPORT_TABS_KEPT - 1


def test_a_same_minute_report_is_replaced_rather_than_rewritten():
    """Rewriting in place would leave the old tab's longer tail below the new rows."""
    assert stale_report_tabs([_report(20)], _report(20)) == [_report(20)]


def test_both_rows_of_a_likely_pair_point_at_each_other():
    published = [
        {"id": "p2", "name": "Jenny Fisk-Becker", "memberships": [_office("Member")]}
    ]
    proposed = [
        {"id": "p3", "name": "Jennifer Fisk-Becker", "memberships": [_office("Member")]}
    ]
    likely = {"p3": "Jenny Fisk-Becker", "p2": "Jennifer Fisk-Becker"}

    jennifer, jenny = [_cells(row) for row in _rows(published, proposed, likely)]

    assert jennifer["name"] == SheetCell(
        value="Jennifer Fisk-Becker", background=ADDED_ROW, note="may be Jenny Fisk-Becker"
    )
    assert jenny["name"] == SheetCell(
        value="Jenny Fisk-Becker", background=ABSENT_ROW, note="may be Jennifer Fisk-Becker"
    )
