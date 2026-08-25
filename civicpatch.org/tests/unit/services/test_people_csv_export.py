"""What a published person looks like as a spreadsheet row.

The row builder is pure, so this needs no mocks: `fetch_people_export_rows` is the DB read
and nothing else.
"""

import pytest
from services.people_csv_export import PEOPLE_CSV_FIELDNAMES, person_row

pytestmark = pytest.mark.unit


def _person(**overrides) -> dict:
    return {
        "jurisdiction_ocdid": "ocd-division/country:us/state:wa/place:buckley",
        "id": "abc",
        "name": "Jane Doe",
        "office": {"name": "Mayor", "division_ocdid": "ocd-division/x"},
        "phones": ["555-0100"],
        "emails": ["jane@example.gov"],
        **overrides,
    }


def test_row_has_exactly_the_declared_columns():
    """DictWriter raises on a key it has no fieldname for, so a row that drifts from
    PEOPLE_CSV_FIELDNAMES fails at download time rather than here."""
    assert set(person_row(_person())) == set(PEOPLE_CSV_FIELDNAMES)


def test_lists_are_joined():
    row = person_row(_person(phones=["555-0100", "555-0199"]))
    assert row["phones"] == "555-0100 | 555-0199"


def test_missing_values_become_empty_strings():
    row = person_row({"id": "abc"})
    assert row["name"] == ""
    assert row["phones"] == ""
    assert row["office_name"] == ""


def test_office_is_flattened_out_of_the_nested_dict():
    row = person_row(_person())
    assert row["office_name"] == "Mayor"
    assert row["office_division_ocdid"] == "ocd-division/x"


@pytest.mark.parametrize("dangerous", ["=cmd|'/c calc'!A1", "+1-555-0100", "-2", "@SUM(A1)"])
def test_formula_prefixes_are_defused(dangerous):
    """A cell opening with one of these is executed by Excel and Sheets. Names and phone
    numbers both reach the file verbatim from a scraped page, so neither is trusted."""
    assert person_row(_person(name=dangerous))["name"].startswith("'")


def test_safe_values_are_left_alone():
    assert person_row(_person())["name"] == "Jane Doe"
