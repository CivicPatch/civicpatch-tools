import pytest

from core.sheet_import_columns import (
    by_row,
    merge_jurisdiction_notes,
    published_other_names_by_person,
    roster_columns,
)
from core.sheet_import_rows import (
    ImportRow,
    RowError,
    Sighting,
    build_jurisdiction_index,
    parse_rows,
)
from core.source_sites import SiteIndex, SiteOwner, build_site_index

_OCDID = "ocd-jurisdiction/country:us/state:ca/place:amador_city/government"
_OCDID_2 = "ocd-jurisdiction/country:us/state:ca/place:menlo_park/government"

# Both towns, as the import knows them: an ocdid is only trusted if it names one of these.
_JURISDICTIONS = build_jurisdiction_index({_OCDID: "0600296", _OCDID_2: "0646870"})


def _row(**overrides) -> dict:
    row = {
        "jurisdiction_ocdid": _OCDID,
        "name": "Ana Reyes",
        "source_url": "https://example.gov/select-board",
        "email": "",
        "phone": "",
        "image": "",
        "label": "Select Board Chair",
    }
    row.update(overrides)
    return row


def _parse(rows: list[dict], sites: SiteIndex = SiteIndex()):
    return parse_rows(rows, sites, _JURISDICTIONS)


def _parsed(*rows: dict):
    parsed, _ = _parse(list(rows))
    return parsed


# ── Columns out ──────────────────────────────────────────────────────────────

_STAMP = "2026-08-27 14:02"


def _parsed_row(
    line: int, ocdid: str = _OCDID, name: str = "Ana Reyes", status: str = ""
) -> ImportRow:
    return ImportRow(
        line=line,
        jurisdiction_ocdid=ocdid,
        sighting=Sighting(name=name, label="Chair", source_url="s"),
        status=status,
    )


def _row_error(line: int, ocdid: str = _OCDID, column: str | None = "name") -> RowError:
    return RowError(line=line, jurisdiction_ocdid=ocdid, column=column, message="required")


def _raw_rows(count: int, overrides: dict[int, dict] | None = None) -> list[dict]:
    """`count` raw sheet rows, line 2..count+1 — the shape `roster_columns` reads its "keep
    whatever this line already said" fallback from, independent of what parsed this run."""
    rows: list[dict] = [{} for _ in range(count)]
    for line, values in (overrides or {}).items():
        rows[line - 2] = values
    return rows


_OTHER_TOWN = "ocd-jurisdiction/country:us/state:zz/place:other/government"


def _named_row(name: str, ocdid: str = _OCDID, note: str = "") -> dict:
    return {"jurisdiction_ocdid": ocdid, "name": name, "note": note}


_SITES = build_site_index(
    [
        SiteOwner(jurisdiction_ocdid=_OCDID, url="https://example.gov"),
        SiteOwner(jurisdiction_ocdid=_OCDID, organization_id="org-schools", url="https://schools.gov"),
        SiteOwner(jurisdiction_ocdid=_OCDID, url="https://shared.gov"),
        SiteOwner(jurisdiction_ocdid=_OCDID_2, url="https://shared.gov"),
    ]
)


@pytest.mark.unit
def test_an_imported_row_says_so_and_carries_no_error():
    columns = roster_columns(_raw_rows(1), [_parsed_row(2)], [], {_OCDID}, _STAMP, {}, {}, set())
    assert columns["status"] == ["imported"]
    assert columns["error"] == [""]


@pytest.mark.unit
def test_a_rejected_row_names_its_column():
    columns = roster_columns(_raw_rows(1), [], [_row_error(2)], set(), _STAMP, {}, {}, set())
    assert columns["status"] == ["error"]
    assert columns["error"] == ["name: required"]


@pytest.mark.unit
def test_a_good_row_in_a_blocked_town_points_elsewhere():
    """Most of a blocked town is rows that are perfectly fine. Saying 'error' against them would
    have the volunteer hunting for a fault that is on somebody else's line."""
    columns = roster_columns(_raw_rows(2), [_parsed_row(2)], [_row_error(3)], set(), _STAMP, {}, {}, set())
    assert columns["status"] == ["blocked", "error"]
    assert columns["error"][0] == "another row in this town was rejected"


@pytest.mark.unit
def test_every_row_gets_a_value_so_stale_errors_clear():
    """A row that failed last run and is fine now must not keep last run's message — the
    volunteer would chase a problem they already fixed."""
    rows = [_parsed_row(2), _parsed_row(3, name="Bo Chen")]
    columns = roster_columns(_raw_rows(2), rows, [], {_OCDID}, _STAMP, {}, {}, set())
    assert columns["error"] == ["", ""]
    assert len(columns["status"]) == 2
    assert columns["last_import_at"] == [_STAMP, _STAMP]


@pytest.mark.unit
def test_a_row_this_run_did_not_touch_keeps_its_status():
    """A jurisdiction already fully handled is skipped before parsing even runs
    (`_handled_jurisdictions`), so this row never becomes an `ImportRow` this pass — and still
    must not be blanked. Status and timestamp both have to come from the sheet's own current
    cells, not from the parse, which saw nothing here at all."""
    raw_rows = _raw_rows(1, {2: {"status": "imported", "last_import_at": "2026-08-01 09:00"}})
    columns = roster_columns(raw_rows, [], [], set(), _STAMP, {}, {}, set())
    assert columns["status"] == ["imported"]
    assert columns["last_import_at"] == ["2026-08-01 09:00"]


@pytest.mark.unit
def test_spare_lines_are_not_stamped():
    """The other half: stop creating the condition. A line the parse produced nothing for gets
    no timestamp, so it stays a line nobody wrote."""
    columns = roster_columns(_raw_rows(3), [], [], set(), _STAMP, {}, {}, set())
    assert columns["last_import_at"] == ["", "", ""]


@pytest.mark.unit
def test_rows_the_run_saw_are_still_stamped():
    parsed, errors = _parse([_row()])
    columns = roster_columns(_raw_rows(1), parsed, errors, {_OCDID}, _STAMP, {}, {}, set())
    assert columns["last_import_at"] == [_STAMP]


@pytest.mark.unit
def test_an_imported_town_gets_each_rows_note_by_name():
    """By name, not line: write-back re-reads the tab, so a row inserted since would shift lines."""
    raw_rows = [_named_row(" Bo Chen "), _named_row("Ana Reyes", note="stale")]
    notes = {(_OCDID, "ana reyes"): "new person", (_OCDID, "bo chen"): "changed: phones"}

    columns = roster_columns(raw_rows, [], [], {_OCDID}, _STAMP, notes, {}, set())

    assert columns["note"] == ["changed: phones", "new person"]


@pytest.mark.unit
def test_a_town_not_imported_this_run_keeps_its_note():
    raw_rows = [_named_row("Ana Reyes", ocdid=_OTHER_TOWN, note="new person")]

    columns = roster_columns(raw_rows, [], [], {_OCDID}, _STAMP, {}, {}, set())

    assert columns["note"] == ["new person"]


@pytest.mark.unit
def test_a_dismissed_import_clears_its_note():
    """Rejected, superseded or expired: the change the note describes can no longer happen."""
    raw_rows = [_named_row("Ana Reyes", ocdid=_OTHER_TOWN, note="new person")]

    columns = roster_columns(raw_rows, [], [], set(), _STAMP, {}, {}, {_OTHER_TOWN})

    assert columns["note"] == [""]


@pytest.mark.unit
def test_a_jurisdiction_note_leads_the_persons_own():
    """One column carries both, and the id that was passed over is the more surprising."""
    rows = _parsed(_row(geoid="9999999"))
    merged = merge_jurisdiction_notes({(_OCDID, "ana reyes"): "new person"}, rows)

    assert merged[(_OCDID, "ana reyes")] == (
        f"matched {_OCDID}; geoid 9999999 names no jurisdiction; new person"
    )


@pytest.mark.unit
def test_a_row_whose_ids_agreed_leaves_the_note_alone():
    rows = _parsed(_row())
    notes = {(_OCDID, "ana reyes"): "new person"}

    assert merge_jurisdiction_notes(notes, rows) == notes


@pytest.mark.unit
def test_no_volunteer_column_is_written_back():
    """A volunteer's columns are theirs. What a blank ocdid resolved to is keyed on internally
    and re-resolved every read, rather than pinned into the cell they left empty."""
    raw_rows = [_row(jurisdiction_ocdid=""), _row(name="Bo Chen", jurisdiction_ocdid=_OCDID)]
    parsed, errors = _parse(raw_rows, _SITES)

    columns = roster_columns(raw_rows, parsed, errors, {_OCDID}, _STAMP, {}, {}, set())

    assert "jurisdiction_ocdid" not in columns
    assert set(columns) == {"status", "error", "last_import_at", "note", "published_other_names"}


@pytest.mark.unit
def test_a_row_no_site_resolved_blocks_no_spare_line():
    """Its error has no town; blocking "" would mark every blank line `blocked`."""
    raw_rows = [_row(jurisdiction_ocdid="", source_url="https://nowhere.gov"), {}]
    parsed, errors = _parse(raw_rows, _SITES)

    columns = roster_columns(raw_rows, parsed, errors, set(), _STAMP, {}, {}, set())

    assert columns["status"] == ["error", ""]


@pytest.mark.unit
def test_an_imported_town_gets_each_rows_published_other_names():
    raw_rows = [_named_row("Jennifer Fisk-Becker"), _named_row("Bo Chen")]
    published = {(_OCDID, "jennifer fisk-becker"): "Jenny Fisk-Becker | J. Fisk-Becker"}

    columns = roster_columns(raw_rows, [], [], {_OCDID}, _STAMP, {}, published, set())

    assert columns["published_other_names"] == ["Jenny Fisk-Becker | J. Fisk-Becker", ""]


@pytest.mark.unit
def test_published_other_names_are_joined_like_the_live_tabs():
    published = [
        {"id": "jenny", "other_names": ["Jenny Fisk-Becker", "Richard T. Hale, Jr."]},
        {"id": "bo", "other_names": []},
    ]

    assert published_other_names_by_person(published) == {
        "jenny": "Jenny Fisk-Becker | Richard T. Hale, Jr.",
        "bo": "",
    }


@pytest.mark.unit
def test_by_row_keys_a_persons_value_by_each_of_their_rows():
    records_by_person = {"jenny": [{"name": "Jennifer Fisk-Becker"}], "new": [{"name": "Bo Chen"}]}

    assert by_row(_OCDID, records_by_person, {"jenny": "Jenny Fisk-Becker"}) == {
        "jennifer fisk-becker": "Jenny Fisk-Becker"
    }
