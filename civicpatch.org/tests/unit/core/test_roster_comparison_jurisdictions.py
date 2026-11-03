import pytest
from pydantic import ValidationError

from core.roster_comparison_jurisdictions import resolve_row, resolve_rows
from schemas.jurisdictions import StateJurisdiction
from schemas.roster_comparisons import IncomingRow, RejectedReason, RejectedRow, UploadedRow

pytestmark = pytest.mark.unit

_PREFIX = "ocd-jurisdiction/country:us/state:vt"
_NOWHERE = f"{_PREFIX}/place:nowhere/government"
_BARRE_CITY = StateJurisdiction(jurisdiction_ocdid=f"{_PREFIX}/place:barre_city/government", name="Barre city", geoid="5003175")
_BARRE_TOWN = StateJurisdiction(jurisdiction_ocdid=f"{_PREFIX}/place:barre_town/government", name="Barre town", geoid="5002303250")
_FAYSTON = StateJurisdiction(jurisdiction_ocdid=f"{_PREFIX}/place:fayston/government", name="Fayston town", geoid="5002325000")
_STATE = [_BARRE_CITY, _BARRE_TOWN, _FAYSTON]


def _row(**fields) -> IncomingRow:
    return IncomingRow(source_row=7, name="Jane Doe", **fields)


def _only(name: str, geoid: str | None = None) -> StateJurisdiction:
    return StateJurisdiction(jurisdiction_ocdid=f"{_PREFIX}/place:only/government", name=name, geoid=geoid)


def _resolved_to(row: IncomingRow, state: list[StateJurisdiction] = _STATE) -> str:
    result = resolve_row(row, state, "vt")
    assert isinstance(result, UploadedRow), result
    return result.jurisdiction_ocdid


def _refused(row: IncomingRow, state: list[StateJurisdiction] = _STATE) -> tuple[RejectedReason, list[str]]:
    result = resolve_row(row, state, "vt")
    assert isinstance(result, RejectedRow), result
    return result.reason, [candidate.jurisdiction_ocdid for candidate in result.candidates]


def _ocdids(*jurisdictions: StateJurisdiction) -> list[str]:
    return [jurisdiction.jurisdiction_ocdid for jurisdiction in jurisdictions]


def test_a_row_must_name_its_jurisdiction_one_way_or_another():
    with pytest.raises(ValidationError, match="jurisdiction_ocdid, geoid or jurisdiction_name"):
        _row()


def test_an_ocdid_decides_alone_whatever_the_geoid_and_name_say():
    row = _row(jurisdiction_ocdid=_FAYSTON.jurisdiction_ocdid, geoid=_BARRE_TOWN.geoid, jurisdiction_name="Barre")

    assert _resolved_to(row) == _FAYSTON.jurisdiction_ocdid


@pytest.mark.parametrize(
    "ocdid, reason",
    [
        (_NOWHERE, RejectedReason.UNKNOWN_JURISDICTION),
        (f"{_PREFIX}/government", RejectedReason.UNKNOWN_JURISDICTION),
        ("ocd-jurisdiction/country:us/state:nh/place:keene/government", RejectedReason.OUTSIDE_STATE),
    ],
)
def test_an_ocdid_the_state_does_not_have_is_refused(ocdid, reason):
    assert _refused(_row(jurisdiction_ocdid=ocdid)) == (reason, [])


def test_a_bad_ocdid_does_not_fall_through_to_a_good_geoid():
    assert _refused(_row(jurisdiction_ocdid=_NOWHERE, geoid=_FAYSTON.geoid)) == (RejectedReason.UNKNOWN_JURISDICTION, [])


def test_a_blank_ocdid_counts_as_absent():
    assert _resolved_to(_row(jurisdiction_ocdid="", geoid=_FAYSTON.geoid)) == _FAYSTON.jurisdiction_ocdid


@pytest.mark.parametrize("name", ["Fayston", "Town of Fayston", "FAYSTON TOWN", "fayston, town of"])
def test_a_name_resolves_with_or_without_its_type(name):
    assert _resolved_to(_row(jurisdiction_name=name)) == _FAYSTON.jurisdiction_ocdid


@pytest.mark.parametrize(
    "file_name, state_name",
    [
        ("Averys Gore", "Avery's Gore"),
        ("Avery’s Gore", "Avery's Gore"),
        ("Espanola", "Española city"),
        ("Winston Salem", "Winston-Salem city"),
        ("Foo", "Foo borough"),
    ],
)
def test_apostrophes_accents_hyphens_and_legal_status_do_not_matter(file_name, state_name):
    jurisdiction = _only(state_name)

    assert _resolved_to(_row(jurisdiction_name=file_name), [jurisdiction]) == jurisdiction.jurisdiction_ocdid


def test_a_type_word_picks_between_two_of_the_same_name():
    assert _resolved_to(_row(jurisdiction_name="Barre City")) == _BARRE_CITY.jurisdiction_ocdid


def test_a_name_that_fits_several_is_refused_with_them():
    assert _refused(_row(jurisdiction_name="Barre")) == (RejectedReason.AMBIGUOUS, _ocdids(_BARRE_CITY, _BARRE_TOWN))


def test_a_place_mentioning_a_county_is_still_a_place():
    place = _only("Lakeside town (Tarrant County)")

    assert _resolved_to(_row(jurisdiction_name="Lakeside town (Tarrant County)"), [place]) == place.jurisdiction_ocdid


@pytest.mark.parametrize("geoid", [5002325000, "5002325000"])
def test_a_geoid_may_arrive_as_a_number_or_text(geoid):
    assert _resolved_to(_row(geoid=geoid)) == _FAYSTON.jurisdiction_ocdid


@pytest.mark.parametrize("name", [None, "Fayston", "Town of Fayston"])
def test_a_geoid_resolves_the_row_when_the_name_agrees_or_is_absent(name):
    assert _resolved_to(_row(geoid=_FAYSTON.geoid, jurisdiction_name=name)) == _FAYSTON.jurisdiction_ocdid


def test_a_geoid_with_or_without_its_leading_zero_is_the_same_geoid():
    california = _only("Alameda city", geoid="0600562")

    assert _resolved_to(_row(geoid="600562"), [california]) == california.jurisdiction_ocdid


@pytest.mark.parametrize("blank_geoid", ["0", "000", "  "])
def test_a_geoid_that_normalizes_to_blank_never_matches_a_jurisdiction_with_no_geoid(blank_geoid):
    assert _refused(_row(geoid=blank_geoid), [_only("Foo town")]) == (RejectedReason.UNKNOWN_GEOID, [])


def test_a_geoid_and_a_name_that_fits_several_resolve_where_they_agree():
    assert _resolved_to(_row(geoid=_BARRE_TOWN.geoid, jurisdiction_name="Barre")) == _BARRE_TOWN.jurisdiction_ocdid


def test_a_geoid_and_name_naming_different_places_are_refused_with_both():
    row = _row(geoid=_BARRE_TOWN.geoid, jurisdiction_name="Fayston")

    assert _refused(row) == (RejectedReason.AMBIGUOUS, _ocdids(_BARRE_TOWN, _FAYSTON))


def test_a_geoid_two_jurisdictions_share_is_refused_with_both():
    shared = _BARRE_TOWN.model_copy(update={"geoid": _BARRE_CITY.geoid})

    assert _refused(_row(geoid=_BARRE_CITY.geoid), [_BARRE_CITY, shared]) == (
        RejectedReason.AMBIGUOUS,
        _ocdids(_BARRE_CITY, _BARRE_TOWN),
    )


@pytest.mark.parametrize(
    "fields, reason, candidates",
    [
        ({"geoid": "9999999"}, RejectedReason.UNKNOWN_GEOID, []),
        ({"geoid": "9999999", "jurisdiction_name": "Fayston"}, RejectedReason.UNKNOWN_GEOID, [_FAYSTON]),
        ({"jurisdiction_name": "Nowhere"}, RejectedReason.UNKNOWN_NAME, []),
        ({"jurisdiction_name": "Town of"}, RejectedReason.UNKNOWN_NAME, []),
        ({"jurisdiction_name": "Fayston City"}, RejectedReason.UNKNOWN_NAME, [_FAYSTON]),
        ({"geoid": _FAYSTON.geoid, "jurisdiction_name": "Fayston Valley"}, RejectedReason.UNKNOWN_NAME, [_FAYSTON]),
        ({"geoid": _FAYSTON.geoid, "jurisdiction_name": "Fayston City"}, RejectedReason.UNKNOWN_NAME, [_FAYSTON]),
    ],
)
def test_a_value_that_names_nothing_is_refused_with_what_the_others_point_to(fields, reason, candidates):
    assert _refused(_row(**fields)) == (reason, _ocdids(*candidates))


def test_the_resolved_row_keeps_the_files_name_and_geoid_as_fields_not_extra_columns():
    result = resolve_row(_row(geoid=_FAYSTON.geoid, jurisdiction_name="Town of Fayston"), _STATE, "vt")

    assert isinstance(result, UploadedRow)
    assert (result.jurisdiction_name, result.geoid) == ("Town of Fayston", _FAYSTON.geoid)
    assert result.not_compared == {}


def test_rows_are_split_into_resolved_and_refused():
    rows = [
        IncomingRow(source_row=2, name="Jane Doe", jurisdiction_name="Fayston"),
        IncomingRow(source_row=3, name="Lee Park", jurisdiction_name="Barre"),
    ]

    resolved, rejected = resolve_rows(rows, _STATE, "vt")

    assert [row.source_row for row in resolved] == [2]
    assert [row.source_row for row in rejected] == [3]
