"""`read_rows` — the one place that decides what "ready" and "blocked" mean.

Pure, so no mocks: the split is a function of the rows alone.
"""

import pytest

from core.sheet_import_rows import build_jurisdiction_index
from core.source_sites import SiteIndex
from services.sheet_import import read_rows

_NO_SITES = SiteIndex()

_TOWN = "ocd-jurisdiction/country:us/state:wa/place:sedro-woolley/government"
_OTHER = "ocd-jurisdiction/country:us/state:wa/place:aberdeen/government"

# Both towns, as the import knows them: an ocdid is only trusted if it names one of these.
_JURISDICTIONS = build_jurisdiction_index({_TOWN: "5363385", _OTHER: "5300100"})


def _row(**overrides) -> dict:
    row = {
        "jurisdiction_ocdid": _TOWN,
        "name": "Jennifer Powers",
        "source_url": "https://example.gov",
        "label": "Mayor",
    }
    row.update(overrides)
    return row


@pytest.mark.unit
def test_a_bad_row_blocks_only_its_own_town():
    """Blocked whole, never partly: importing the good rows of a bad town proposes a roster
    missing somebody, which review then reads as a departure."""
    read = read_rows(
        [
            _row(name=""),
            _row(jurisdiction_ocdid=_OTHER, name="Ada Whitfield", label="Mayor"),
        ],
        _NO_SITES,
        _JURISDICTIONS,
    )

    assert read.preview.jurisdictions_blocked == [_TOWN]
    assert read.preview.jurisdictions_ready == [_OTHER]
    assert [(e.line, e.column) for e in read.preview.errors] == [(2, "name")]


@pytest.mark.unit
def test_a_blocked_towns_rows_do_not_reach_the_import():
    """The preview says blocked and the payload agrees — `rows` is what actually gets written."""
    read = read_rows(
        [
            _row(name=""),
            _row(name="Bo Nunez", label="Mayor"),
            _row(jurisdiction_ocdid=_OTHER, name="Ada Whitfield", label="Mayor"),
        ],
        _NO_SITES,
        _JURISDICTIONS,
    )

    assert [row.jurisdiction_ocdid for row in read.rows] == [_OTHER]
