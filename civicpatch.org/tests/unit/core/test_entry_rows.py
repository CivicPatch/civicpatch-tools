import pytest

from core.entry_rows import (
    INHERIT,
    ImportRow,
    RowError,
    Sighting,
    already_handled,
    parse_rows,
    roster_columns,
    rows_by_jurisdiction,
)

_OCDID = "ocd-jurisdiction/country:us/state:ca/place:amador_city/government"
_OCDID_2 = "ocd-jurisdiction/country:us/state:ca/place:menlo_park/government"


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


def _flags(errors) -> set:
    return {(error.line, error.column) for error in errors}


# --- the happy path ---


@pytest.mark.unit
def test_a_row_becomes_a_sighting():
    rows, errors = parse_rows([_row()])
    assert errors == []
    assert rows[0].sighting.name == "Ana Reyes"
    assert rows[0].sighting.source_url == "https://example.gov/select-board"
    assert rows[0].jurisdiction_ocdid == _OCDID


@pytest.mark.unit
def test_a_blank_label_is_required():
    """A blank cell is a caught mistake now, not silent — a source with no title has to say so
    on purpose, with `inherit`."""
    _, errors = parse_rows([_row(label="")])
    assert _flags(errors) == {(2, "label")}


@pytest.mark.unit
def test_inherit_passes_through_as_a_marker():
    """Resolving it needs a database read — `services.sheet_import`'s job, not this pure
    module's. This only has to not mangle it on the way through."""
    rows, errors = parse_rows([_row(label=INHERIT)])
    assert errors == []
    assert rows[0].sighting.label == INHERIT


@pytest.mark.unit
def test_inherit_is_case_insensitive():
    rows, _ = parse_rows([_row(label="Inherit")])
    assert rows[0].sighting.label == INHERIT


@pytest.mark.unit
def test_a_present_label_still_works():
    rows, _ = parse_rows([_row(label="Select Board Chair")])
    assert rows[0].sighting.label == "Select Board Chair"


@pytest.mark.unit
def test_line_numbers_count_the_header():
    """They have to match the row gutter a volunteer is looking at."""
    rows, _ = parse_rows([_row(), _row(name="Bo Chen")])
    assert [row.line for row in rows] == [2, 3]


@pytest.mark.unit
def test_blanks_become_none_and_whitespace_is_stripped():
    rows, _ = parse_rows([_row(name="  Ana Reyes  ", phone="  ", email="a@b.gov")])
    assert rows[0].sighting.name == "Ana Reyes"
    assert rows[0].sighting.phone is None
    assert rows[0].sighting.email == "a@b.gov"


@pytest.mark.unit
def test_the_sheet_carries_no_ids():
    """Matching is ingest's job. A uuid in a cell would let a curator mis-seat somebody with a
    value nothing can validate, so the model has nowhere to put one."""
    rows, _ = parse_rows([_row(person_id="anything", post_id="anything")])
    assert not hasattr(rows[0], "person_id")
    assert not hasattr(rows[0].sighting, "post_id")


# --- what blocks a row ---


@pytest.mark.unit
@pytest.mark.parametrize("column", ["jurisdiction_ocdid", "name", "source_url", "label"])
def test_the_required_columns(column):
    _, errors = parse_rows([_row(**{column: ""})])
    assert _flags(errors) == {(2, column)}


@pytest.mark.unit
@pytest.mark.parametrize(
    "column,value",
    [
        ("phone", "not-a-number"),
        ("email", "missing-the-at-sign"),
        ("source_url", "example.gov"),
        ("source_url", "http://localhost"),
    ],
)
def test_contact_columns_are_checked_here_not_further_down(column, value):
    """The same rules `SubmittedPersonRecord` applies, run at the row so a volunteer sees the bad
    cell in their sheet. Before this the three passed through unchecked."""
    _, errors = parse_rows([_row(**{column: value})])
    assert _flags(errors) == {(2, column)}


@pytest.mark.unit
@pytest.mark.parametrize(
    "column,value",
    [
        ("phone", "206-684-4000"),
        ("email", "clerk@example.gov"),
    ],
)
def test_a_contact_column_that_is_fine_is_left_alone(column, value):
    _, errors = parse_rows([_row(**{column: value})])
    assert errors == []


@pytest.mark.unit
def test_an_empty_contact_column_is_not_an_error():
    """All three are optional — absent is not the same as wrong."""
    _, errors = parse_rows([_row(phone="", email="")])
    assert errors == []


@pytest.mark.unit
def test_one_bad_row_does_not_cost_the_others_their_turn():
    rows, errors = parse_rows([_row(), _row(name=""), _row(name="Bo Chen")])
    assert [row.line for row in rows] == [2, 4]
    assert _flags(errors) == {(3, "name")}


# --- one person, one seat ---


@pytest.mark.unit
def test_the_same_person_twice_in_one_jurisdiction_is_an_error():
    """`memberships` has a unique index on (person_id, organization_id) among open rows and a
    jurisdiction has one organization, so two rows for one person is unrepresentable."""
    _, errors = parse_rows([_row(), _row(label="Chair")])
    assert _flags(errors) == {(3, "name")}
    assert "line 2" in errors[0].message


@pytest.mark.unit
def test_duplicate_detection_ignores_case():
    _, errors = parse_rows([_row(name="Ana Reyes"), _row(name="ana reyes")])
    assert _flags(errors) == {(3, "name")}


@pytest.mark.unit
def test_the_same_name_in_two_jurisdictions_is_ordinary():
    _, errors = parse_rows([_row(), _row(jurisdiction_ocdid=_OCDID_2)])
    assert errors == []


# --- grouping ---


@pytest.mark.unit
def test_rows_group_by_jurisdiction():
    rows, _ = parse_rows(
        [_row(), _row(name="Bo Chen"), _row(jurisdiction_ocdid=_OCDID_2)]
    )
    grouped = rows_by_jurisdiction(rows)
    assert sorted(grouped) == sorted([_OCDID, _OCDID_2])
    assert len(grouped[_OCDID]) == 2


# --- already-handled jurisdictions are skipped before validation ---


@pytest.mark.unit
def test_a_fully_handled_jurisdiction_is_skipped_even_if_invalid_now():
    """A contract change made after a row was accepted (a new required column, say) must not
    re-reject it forever — clearing its status is the only thing that should ask for it again."""
    rows, errors = parse_rows([_row(label="", status="imported")])
    assert rows == []
    assert errors == []


@pytest.mark.unit
def test_a_mixed_jurisdiction_is_not_skipped():
    """One cleared row brings the whole town back — including rows still carrying a status, so
    the roster submitted together is complete, not missing whoever already had one."""
    rows, errors = parse_rows([_row(status="imported"), _row(name="Bo Chen", status="")])
    assert [row.sighting.name for row in rows] == ["Ana Reyes", "Bo Chen"]
    assert errors == []


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


# --- roster tab ---


@pytest.mark.unit
def test_an_imported_row_says_so_and_carries_no_error():
    columns = roster_columns(_raw_rows(1), [_parsed_row(2)], [], {_OCDID}, _STAMP)
    assert columns["status"] == ["imported"]
    assert columns["error"] == [""]


@pytest.mark.unit
def test_a_rejected_row_names_its_column():
    columns = roster_columns(_raw_rows(1), [], [_row_error(2)], set(), _STAMP)
    assert columns["status"] == ["error"]
    assert columns["error"] == ["name: required"]


@pytest.mark.unit
def test_a_good_row_in_a_blocked_town_points_elsewhere():
    """Most of a blocked town is rows that are perfectly fine. Saying 'error' against them would
    have the volunteer hunting for a fault that is on somebody else's line."""
    columns = roster_columns(_raw_rows(2), [_parsed_row(2)], [_row_error(3)], set(), _STAMP)
    assert columns["status"] == ["blocked", "error"]
    assert columns["error"][0] == "another row in this town was rejected"


@pytest.mark.unit
def test_every_row_gets_a_value_so_stale_errors_clear():
    """A row that failed last run and is fine now must not keep last run's message — the
    volunteer would chase a problem they already fixed."""
    rows = [_parsed_row(2), _parsed_row(3, name="Bo Chen")]
    columns = roster_columns(_raw_rows(2), rows, [], {_OCDID}, _STAMP)
    assert columns["error"] == ["", ""]
    assert len(columns["status"]) == 2
    assert columns["last_import_at"] == [_STAMP, _STAMP]


# --- the status column decides whether a locality is re-imported ---
#
# Tested directly on `ImportRow`s, not through `parse_rows`: a fully-handled jurisdiction is
# now skipped before parsing even runs (`_handled_jurisdictions`, tested above), so building
# these through `parse_rows` would just hand `already_handled` an empty list and pass on that
# vacuous truth instead of exercising it. `import_rows` still calls `already_handled` directly
# as a second, defensive check, so it stays worth testing on its own.


def _parsed(*rows: dict):
    parsed, errors = parse_rows(list(rows))
    assert errors == []
    return parsed


@pytest.mark.unit
def test_a_locality_whose_rows_all_say_imported_is_done():
    rows = [_parsed_row(2, status="imported"), _parsed_row(3, name="Bo", status="imported")]
    assert already_handled(rows)


@pytest.mark.unit
def test_a_blank_status_brings_the_locality_back():
    """What a volunteer does after fixing a row: clear the cell, press Import."""
    rows = [_parsed_row(2, status="imported"), _parsed_row(3, name="Bo", status="")]
    assert not already_handled(rows)


@pytest.mark.unit
def test_any_status_counts_as_handled_not_just_imported():
    """The column is the app's account of what it did. `error` and `blocked` have been answered
    for too — the volunteer clears the cell to ask again."""
    assert already_handled([_parsed_row(2, status="error")])
    assert already_handled([_parsed_row(2, status="blocked")])


@pytest.mark.unit
def test_a_row_this_run_did_not_touch_keeps_its_status():
    """A jurisdiction already fully handled is skipped before parsing even runs
    (`_handled_jurisdictions`), so this row never becomes an `ImportRow` this pass — and still
    must not be blanked. Status and timestamp both have to come from the sheet's own current
    cells, not from the parse, which saw nothing here at all."""
    raw_rows = _raw_rows(1, {2: {"status": "imported", "last_import_at": "2026-08-01 09:00"}})
    columns = roster_columns(raw_rows, [], [], set(), _STAMP)
    assert columns["status"] == ["imported"]
    assert columns["last_import_at"] == ["2026-08-01 09:00"]


@pytest.mark.unit
def test_a_never_imported_locality_has_no_status_at_all():
    assert not already_handled([_parsed_row(2, status="")])


@pytest.mark.unit
def test_one_row_wanting_attention_brings_the_whole_roster():
    """All, not any. A card carrying only the cleared row would propose closing everybody
    else's membership when published."""
    rows = _parsed(_row(status="imported"), _row(name="Bo", status=""))
    assert not already_handled(rows)
    assert len(rows) == 2


@pytest.mark.unit
def test_blank_rows_are_grid_not_errors():
    """Sheets returns every line in the used range. A tab with four entries and 140 spare lines
    was reporting 420 `required` errors and blocking both jurisdictions on rows nobody typed."""
    blank = {column: "" for column in _row()}
    parsed, errors = parse_rows([_row(), blank, blank, blank])
    assert len(parsed) == 1
    assert errors == []


@pytest.mark.unit
def test_a_half_filled_row_is_still_an_error():
    """The distinction that matters: somebody picked a jurisdiction and stopped. That is a row
    they meant to write, and telling them about it is the point."""
    started = {column: "" for column in _row()}
    started["jurisdiction_ocdid"] = _OCDID
    _, errors = parse_rows([started])
    assert {column for _, column in _flags(errors)} == {"name", "source_url", "label"}


@pytest.mark.unit
def test_line_numbers_survive_skipped_blanks():
    """Blank rows still occupy a line, so a row after one must keep the gutter number the
    volunteer sees."""
    blank = {column: "" for column in _row()}
    parsed, _ = parse_rows([blank, blank, _row()])
    assert [row.line for row in parsed] == [4]


@pytest.mark.unit
def test_a_stamped_but_untyped_row_is_still_blank():
    """The bug this actually was. The write-back stamped `last_import_at` down the used range,
    so every spare line carried a timestamp — and a blankness check over all values then read
    143 empty lines as occupied and rejected each three times."""
    stamped = {column: "" for column in _row()}
    stamped["last_import_at"] = "2026-09-03 22:41"
    parsed, errors = parse_rows([_row(), stamped])
    assert len(parsed) == 1
    assert errors == []


@pytest.mark.unit
def test_spare_lines_are_not_stamped():
    """The other half: stop creating the condition. A line the parse produced nothing for gets
    no timestamp, so it stays a line nobody wrote."""
    columns = roster_columns(_raw_rows(3), [], [], set(), _STAMP)
    assert columns["last_import_at"] == ["", "", ""]


@pytest.mark.unit
def test_rows_the_run_saw_are_still_stamped():
    parsed, errors = parse_rows([_row()])
    columns = roster_columns(_raw_rows(1), parsed, errors, {_OCDID}, _STAMP)
    assert columns["last_import_at"] == [_STAMP]
