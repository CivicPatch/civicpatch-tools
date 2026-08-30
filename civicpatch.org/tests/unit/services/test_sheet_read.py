"""`read_rows` — the one place that decides what "ready" and "blocked" mean.

Pure, so no mocks: the split is a function of the rows alone.
"""

import pytest

from services.sheet_import import read_rows

_TOWN = "ocd-jurisdiction/country:us/state:wa/place:sedro-woolley/government"
_OTHER = "ocd-jurisdiction/country:us/state:wa/place:aberdeen/government"


@pytest.mark.unit
def test_a_bad_row_blocks_only_its_own_town():
    """Blocked whole, never partly: importing the good rows of a bad town proposes a roster
    missing somebody, which review then reads as a departure."""
    read = read_rows(
        [
            {"jurisdiction_ocdid": _TOWN, "name": "Jennifer Powers", "label": ""},
            {"jurisdiction_ocdid": _OTHER, "name": "Ada Whitfield", "label": "Mayor"},
        ],
        "s",
    )

    assert read.preview.jurisdictions_blocked == [_TOWN]
    assert read.preview.jurisdictions_ready == [_OTHER]
    assert [(e.line, e.column) for e in read.preview.errors] == [(2, "label")]


@pytest.mark.unit
def test_a_blocked_towns_rows_do_not_reach_the_import():
    """The preview says blocked and the payload agrees — `rows` is what actually gets written."""
    read = read_rows(
        [
            {"jurisdiction_ocdid": _TOWN, "name": "Jennifer Powers", "label": ""},
            {"jurisdiction_ocdid": _TOWN, "name": "Bo Nunez", "label": "Mayor"},
            {"jurisdiction_ocdid": _OTHER, "name": "Ada Whitfield", "label": "Mayor"},
        ],
        "s",
    )

    assert [row.jurisdiction_ocdid for row in read.rows] == [_OTHER]
