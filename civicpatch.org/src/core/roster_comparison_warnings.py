"""What a reader should be warned about on one uploaded row, whatever it matched."""

from shared.utils.email_utils import is_valid_email
from shared.utils.phone_utils import normalize_phone_number
from shared.utils.taxonomy import Taxonomy

from core.roster_comparison_fields import role_not_recognised
from schemas.roster_comparisons import Candidate, RowWarning, RowWarningCode, UploadedRow


def row_warnings(row: UploadedRow, candidates: list[Candidate], taxonomy: Taxonomy) -> list[RowWarning]:
    return [
        *_already_matched(candidates),
        *_role_not_recognised(row.role, taxonomy),
        *[_warning(RowWarningCode.INVALID_EMAIL, f"'{value}' is not an email address")
          for value in row.emails if not is_valid_email(value.strip())],
        *[_warning(RowWarningCode.INVALID_PHONE, f"'{value}' is not a phone number")
          for value in row.phones if normalize_phone_number(value) is None],
    ]


def _already_matched(candidates: list[Candidate]) -> list[RowWarning]:
    return [
        _warning(
            RowWarningCode.CANDIDATE_ALREADY_MATCHED,
            f"{candidate.name} is already matched to row {candidate.already_matched_by_row}",
        )
        for candidate in candidates
        if candidate.already_matched_by_row is not None
    ]


def _role_not_recognised(role: str | None, taxonomy: Taxonomy) -> list[RowWarning]:
    if not role_not_recognised(role, taxonomy):
        return []
    message = f"Role '{(role or '').strip()}' is not a role civicpatch knows"
    return [_warning(RowWarningCode.ROLE_NOT_RECOGNISED, message)]


def _warning(code: RowWarningCode, message: str) -> RowWarning:
    return RowWarning(code=code, message=message)
