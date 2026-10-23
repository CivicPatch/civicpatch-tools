import pytest
from shared.schemas import Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison_warnings import row_warnings
from schemas.roster_comparisons import Candidate, CandidateReason, RowWarningCode, UploadedRow

TAXONOMY = build_taxonomy(RoleConfig(roles=[Role(id="member", label="Member", aliases=["Council Member"])]))
_JURISDICTION = "ocd-jurisdiction/country:us/state:vt/place:barre/government"


def _row(**fields) -> UploadedRow:
    return UploadedRow(source_row=7, jurisdiction_ocdid=_JURISDICTION, name="Jane Doe", **fields)


def _codes(row: UploadedRow, candidates=()) -> list[RowWarningCode]:
    return [warning.code for warning in row_warnings(row, list(candidates), TAXONOMY)]


@pytest.mark.unit
def test_a_clean_row_has_no_warnings():
    row = _row(role="Council Member", emails=["jdoe@barre.gov"], phones=["802-555-0134"])

    assert _codes(row) == []


@pytest.mark.unit
def test_a_candidate_another_row_matched_is_named_in_the_warning():
    candidate = Candidate(person_id="j", name="Jane Doe", reason=CandidateReason.SAME_NAME, already_matched_by_row=2)

    [warning] = row_warnings(_row(), [candidate], TAXONOMY)

    assert warning.code is RowWarningCode.CANDIDATE_ALREADY_MATCHED
    assert warning.message == "Jane Doe is already matched to row 2"


@pytest.mark.unit
def test_an_unknown_role_is_warned_about():
    assert _codes(_row(role="Keeper of the Pound")) == [RowWarningCode.ROLE_NOT_RECOGNISED]


@pytest.mark.unit
def test_values_that_are_not_emails_or_phones_are_warned_about():
    row = _row(emails=["call the office"], phones=["ext. 4"])

    assert _codes(row) == [RowWarningCode.INVALID_EMAIL, RowWarningCode.INVALID_PHONE]
