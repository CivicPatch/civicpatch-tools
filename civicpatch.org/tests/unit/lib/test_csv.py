import pytest

from lib.csv import generate_csv, parse_csv, sanitize


@pytest.mark.unit
def test_rows_are_keyed_by_the_header():
    rows = parse_csv("name,label\nAna Reyes,Select Board Chair\n")
    assert rows == [{"name": "Ana Reyes", "label": "Select Board Chair"}]


@pytest.mark.unit
def test_headers_are_stripped_and_lowercased():
    """A header row is typed by a human, so `Jurisdiction_OCDID ` and `jurisdiction_ocdid`
    have to be the same column."""
    rows = parse_csv(" Name , LABEL\nAna Reyes,Chair\n")
    assert rows == [{"name": "Ana Reyes", "label": "Chair"}]


@pytest.mark.unit
def test_a_header_only_file_has_no_rows():
    assert parse_csv("name,label\n") == []


@pytest.mark.unit
def test_an_empty_file_is_not_an_error():
    assert parse_csv("") == []


@pytest.mark.unit
def test_quoted_commas_and_newlines_survive():
    rows = parse_csv('name,label\n"Reyes, Ana","Chair\nand Clerk"\n')
    assert rows[0]["name"] == "Reyes, Ana"
    assert rows[0]["label"] == "Chair\nand Clerk"


@pytest.mark.unit
def test_a_short_row_leaves_the_missing_field_none():
    """`csv` pads rather than raising, and the parser above turns that into an empty string so
    every value is text."""
    rows = parse_csv("name,label\nAna Reyes\n")
    assert rows[0] == {"name": "Ana Reyes", "label": ""}


@pytest.mark.unit
def test_the_formula_guard_round_trips():
    """`sanitize` prefixes a `'` on export; reading our own export back must return what went
    in, not the escape."""
    dangerous = "=SUM(A1:A2)"
    assert parse_csv(f"label\n{sanitize(dangerous)}\n")[0]["label"] == dangerous


@pytest.mark.unit
def test_export_and_read_back_are_inverses():
    fieldnames = ["name", "label"]
    written = "".join(
        generate_csv([{"name": "Ana Reyes", "label": "Chair"}], fieldnames)
    )
    assert parse_csv(written) == [{"name": "Ana Reyes", "label": "Chair"}]
