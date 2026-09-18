import pytest

from core.sheet_import_rows import (
    ImportRow,
    Sighting,
    already_handled,
    parse_rows,
    rows_by_jurisdiction,
)
from core.source_sites import SiteIndex, SiteOwner, build_site_index

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


def _parse(rows: list[dict], sites: SiteIndex = SiteIndex()):
    return parse_rows(rows, sites)


def _flags(errors) -> set:
    return {(error.line, error.column) for error in errors}


def _parsed_row(
    line: int, ocdid: str = _OCDID, name: str = "Ana Reyes", status: str = ""
) -> ImportRow:
    return ImportRow(
        line=line,
        jurisdiction_ocdid=ocdid,
        sighting=Sighting(name=name, label="Chair", source_url="s"),
        status=status,
    )


def _parsed(*rows: dict):
    parsed, errors = _parse(list(rows))
    assert errors == []
    return parsed


_SITES = build_site_index(
    [
        SiteOwner(jurisdiction_ocdid=_OCDID, url="https://example.gov"),
        SiteOwner(jurisdiction_ocdid=_OCDID, organization_id="org-schools", url="https://schools.gov"),
        SiteOwner(jurisdiction_ocdid=_OCDID, url="https://shared.gov"),
        SiteOwner(jurisdiction_ocdid=_OCDID_2, url="https://shared.gov"),
    ]
)


@pytest.mark.unit
def test_a_row_becomes_a_sighting():
    rows, errors = _parse([_row()])
    assert errors == []
    assert rows[0].sighting.name == "Ana Reyes"
    assert rows[0].sighting.source_url == "https://example.gov/select-board"
    assert rows[0].jurisdiction_ocdid == _OCDID


@pytest.mark.unit
def test_a_blank_label_is_allowed():
    """A sheet import states only what it fills in: a blank label keeps the person's current
    post (`people_roster.partial_roster`), so it is not a mistake to catch."""
    rows, errors = _parse([_row(label="")])
    assert errors == []
    assert rows[0].sighting.label == ""


@pytest.mark.unit
def test_a_present_label_still_works():
    rows, _ = _parse([_row(label="Select Board Chair")])
    assert rows[0].sighting.label == "Select Board Chair"


@pytest.mark.unit
def test_line_numbers_count_the_header():
    """They have to match the row gutter a volunteer is looking at."""
    rows, _ = _parse([_row(), _row(name="Bo Chen")])
    assert [row.line for row in rows] == [2, 3]


@pytest.mark.unit
def test_blanks_become_none_and_whitespace_is_stripped():
    rows, _ = _parse([_row(name="  Ana Reyes  ", phone="  ", email="a@b.gov")])
    assert rows[0].sighting.name == "Ana Reyes"
    assert rows[0].sighting.phone is None
    assert rows[0].sighting.email == "a@b.gov"


@pytest.mark.unit
def test_the_sheet_carries_no_ids():
    """Matching is ingest's job. A uuid in a cell would let a curator mis-seat somebody with a
    value nothing can validate, so the model has nowhere to put one."""
    rows, _ = _parse([_row(person_id="anything", post_id="anything")])
    assert not hasattr(rows[0], "person_id")
    assert not hasattr(rows[0].sighting, "post_id")


@pytest.mark.unit
@pytest.mark.parametrize("column", ["name", "source_url"])
def test_the_required_columns(column):
    _, errors = _parse([_row(**{column: ""})])
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
    _, errors = _parse([_row(**{column: value})])
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
    _, errors = _parse([_row(**{column: value})])
    assert errors == []


@pytest.mark.unit
def test_an_empty_contact_column_is_not_an_error():
    """All three are optional — absent is not the same as wrong."""
    _, errors = _parse([_row(phone="", email="")])
    assert errors == []


@pytest.mark.unit
def test_one_bad_row_does_not_cost_the_others_their_turn():
    rows, errors = _parse([_row(), _row(name=""), _row(name="Bo Chen")])
    assert [row.line for row in rows] == [2, 4]
    assert _flags(errors) == {(3, "name")}


@pytest.mark.unit
def test_the_same_person_twice_in_one_jurisdiction_is_an_error():
    """`memberships` has a unique index on (person_id, organization_id) among open rows and a
    jurisdiction has one organization, so two rows for one person is unrepresentable."""
    _, errors = _parse([_row(), _row(label="Chair")])
    assert _flags(errors) == {(3, "name")}
    assert "line 2" in errors[0].message


@pytest.mark.unit
def test_duplicate_detection_ignores_case():
    _, errors = _parse([_row(name="Ana Reyes"), _row(name="ana reyes")])
    assert _flags(errors) == {(3, "name")}


@pytest.mark.unit
def test_the_same_name_in_two_jurisdictions_is_ordinary():
    _, errors = _parse([_row(), _row(jurisdiction_ocdid=_OCDID_2)])
    assert errors == []


@pytest.mark.unit
def test_rows_group_by_jurisdiction():
    rows, _ = _parse(
        [_row(), _row(name="Bo Chen"), _row(jurisdiction_ocdid=_OCDID_2)]
    )
    grouped = rows_by_jurisdiction(rows)
    assert sorted(grouped) == sorted([_OCDID, _OCDID_2])
    assert len(grouped[_OCDID]) == 2


@pytest.mark.unit
def test_a_fully_handled_jurisdiction_is_skipped_even_if_invalid_now():
    """A contract change made after a row was accepted (a new required column, say) must not
    re-reject it forever — clearing its status is the only thing that should ask for it again."""
    rows, errors = _parse([_row(label="", status="imported")])
    assert rows == []
    assert errors == []


@pytest.mark.unit
def test_a_mixed_jurisdiction_is_not_skipped():
    """One cleared row brings the whole town back — including rows still carrying a status, so
    the roster submitted together is complete, not missing whoever already had one."""
    rows, errors = _parse([_row(status="imported"), _row(name="Bo Chen", status="")])
    assert [row.sighting.name for row in rows] == ["Ana Reyes", "Bo Chen"]
    assert errors == []


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
    parsed, errors = _parse([_row(), blank, blank, blank])
    assert len(parsed) == 1
    assert errors == []


@pytest.mark.unit
def test_a_half_filled_row_is_still_an_error():
    """The distinction that matters: somebody picked a jurisdiction and stopped. That is a row
    they meant to write, and telling them about it is the point."""
    started = {column: "" for column in _row()}
    started["jurisdiction_ocdid"] = _OCDID
    _, errors = _parse([started])
    assert {column for _, column in _flags(errors)} == {"name", "source_url"}


@pytest.mark.unit
def test_line_numbers_survive_skipped_blanks():
    """Blank rows still occupy a line, so a row after one must keep the gutter number the
    volunteer sees."""
    blank = {column: "" for column in _row()}
    parsed, _ = _parse([blank, blank, _row()])
    assert [row.line for row in parsed] == [4]


@pytest.mark.unit
def test_a_stamped_but_untyped_row_is_still_blank():
    """The bug this actually was. The write-back stamped `last_import_at` down the used range,
    so every spare line carried a timestamp — and a blankness check over all values then read
    143 empty lines as occupied and rejected each three times."""
    stamped = {column: "" for column in _row()}
    stamped["last_import_at"] = "2026-09-03 22:41"
    parsed, errors = _parse([_row(), stamped])
    assert len(parsed) == 1
    assert errors == []


@pytest.mark.unit
def test_a_blank_jurisdiction_is_the_one_whose_site_the_source_is_on():
    [row], errors = _parse([_row(jurisdiction_ocdid="")], _SITES)

    assert errors == []
    assert row.jurisdiction_ocdid == _OCDID
    assert row.sighting.organization_id is None


@pytest.mark.unit
def test_a_source_on_a_bodys_site_takes_that_body():
    [row], _ = _parse(
        [_row(jurisdiction_ocdid="", source_url="https://schools.gov/board")], _SITES
    )

    assert row.sighting.organization_id == "org-schools"


@pytest.mark.unit
def test_a_typed_jurisdiction_still_takes_the_body_whose_site_it_is():
    [row], _ = _parse([_row(source_url="https://schools.gov/board")], _SITES)

    assert (row.jurisdiction_ocdid, row.sighting.organization_id) == (_OCDID, "org-schools")


@pytest.mark.unit
@pytest.mark.parametrize(
    "source_url,expected",
    [
        ("https://nowhere.gov/council", "no jurisdiction's website matches nowhere.gov"),
        ("https://shared.gov/council", "shared.gov is the website of 2 jurisdictions"),
    ],
)
def test_a_site_that_names_no_single_jurisdiction_asks_for_one(source_url, expected):
    _, [error] = _parse([_row(jurisdiction_ocdid="", source_url=source_url)], _SITES)

    assert error.column == "jurisdiction_ocdid"
    assert error.message.startswith(expected)
