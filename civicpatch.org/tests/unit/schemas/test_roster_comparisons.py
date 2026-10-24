import pytest
from pydantic import ValidationError

from schemas.roster_comparisons import MAX_ROWS, RosterComparisonUpload, UploadedRow

_ROW = {
    "source_row": 4,
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:vt/place:barre/government",
    "name": "Jane Doe",
}


def _upload(**overrides) -> dict:
    return {
        "state": "vt",
        "source_columns": {"name": ["Official"]},
        "corrections": [],
        "rows": [_ROW],
        **overrides,
    }


def _error_fields(error: ValidationError) -> set[str]:
    return {".".join(str(part) for part in item["loc"]) for item in error.errors()}


@pytest.mark.unit
def test_an_upload_without_corrections_is_refused_naming_the_field():
    body = _upload()
    del body["corrections"]

    with pytest.raises(ValidationError) as error:
        RosterComparisonUpload.model_validate(body)

    assert "corrections" in _error_fields(error.value)


@pytest.mark.unit
def test_an_empty_corrections_list_is_valid():
    assert RosterComparisonUpload.model_validate(_upload()).corrections == []


@pytest.mark.unit
def test_a_row_without_source_row_is_refused():
    row = {key: value for key, value in _ROW.items() if key != "source_row"}

    with pytest.raises(ValidationError) as error:
        UploadedRow.model_validate(row)

    assert "source_row" in _error_fields(error.value)


@pytest.mark.unit
def test_a_column_we_do_not_model_lands_in_not_compared():
    row = UploadedRow.model_validate({**_ROW, "Organization": "Select Board", "ward": 2})

    assert row.not_compared == {"Organization": "Select Board", "ward": 2}


@pytest.mark.unit
def test_a_state_must_be_a_two_letter_code():
    with pytest.raises(ValidationError):
        RosterComparisonUpload.model_validate(_upload(state="Vermont"))


@pytest.mark.unit
def test_an_uppercase_state_is_lowercased():
    assert RosterComparisonUpload.model_validate(_upload(state="VT")).state == "vt"


@pytest.mark.unit
def test_more_rows_than_the_cap_are_refused():
    with pytest.raises(ValidationError):
        RosterComparisonUpload.model_validate(_upload(rows=[_ROW] * (MAX_ROWS + 1)))


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "x" * 301},
        {"name": "Jane\x00Doe"},
        {"emails": ["a@b.gov"] * 21},
        {"source_row": 2_147_483_648},
        {"Ward": {"nested": "dict"}},
    ],
    ids=["name too long", "NUL character", "too many emails", "row number past integer", "nested extra column"],
)
def test_a_row_past_the_limits_is_refused_before_it_is_stored(overrides):
    with pytest.raises(ValidationError):
        UploadedRow.model_validate({**_ROW, **overrides})


@pytest.mark.unit
def test_too_many_extra_columns_are_refused():
    extras = {f"Column {n}": "x" for n in range(51)}

    with pytest.raises(ValidationError):
        UploadedRow.model_validate({**_ROW, **extras})
