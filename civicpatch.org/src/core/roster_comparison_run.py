"""A whole upload into one run: rows grouped by jurisdiction, each compared; and the rows that name no
jurisdiction of the state, which refuse an upload before it is compared."""

from shared.schemas import Person
from shared.utils.taxonomy import Taxonomy

from core.roster_comparison import compare_people
from core.roster_comparison_rates import rates, total
from schemas.roster_comparisons import (
    JurisdictionComparison,
    RejectedReason,
    RejectedRow,
    RosterComparison,
    RosterComparisonUpload,
    UploadedRow,
)


def build_comparison(
    upload: RosterComparisonUpload,
    state_ocdids: set[str],
    rosters: dict[str, list[Person]],
    taxonomy: Taxonomy,
) -> RosterComparison:
    """Every row names one of `state_ocdids` (checked before, `rejected_rows`); `rosters` holds the
    people with an open membership in those the upload names."""
    rows_by_ocdid = _rows_by_ocdid(upload.rows)
    jurisdictions = [
        _jurisdiction(ocdid, rows, rosters.get(ocdid, []), taxonomy)
        for ocdid, rows in rows_by_ocdid.items()
    ]
    return RosterComparison(
        state=upload.state,
        source_columns=upload.source_columns,
        corrections=upload.corrections,
        rates=total([jurisdiction.rates for jurisdiction in jurisdictions]),
        jurisdictions_not_named=len(state_ocdids - rows_by_ocdid.keys()),
        jurisdictions=jurisdictions,
    )


def _rows_by_ocdid(rows: list[UploadedRow]) -> dict[str, list[UploadedRow]]:
    grouped: dict[str, list[UploadedRow]] = {}
    for row in rows:
        grouped.setdefault(row.jurisdiction_ocdid, []).append(row)
    return grouped


def _jurisdiction(
    ocdid: str, rows: list[UploadedRow], roster: list[Person], taxonomy: Taxonomy
) -> JurisdictionComparison:
    people = compare_people(rows, roster, taxonomy)
    return JurisdictionComparison(jurisdiction_ocdid=ocdid, rates=rates(people), people=people)


def rejected_rows(rows: list[UploadedRow], state_ocdids: set[str], state: str) -> list[RejectedRow]:
    return [_rejected(row, state) for row in rows if row.jurisdiction_ocdid not in state_ocdids]


def _rejected(row: UploadedRow, state: str) -> RejectedRow:
    in_state = f"state:{state}" in row.jurisdiction_ocdid.split("/")
    return RejectedRow(
        source_row=row.source_row,
        jurisdiction_ocdid=row.jurisdiction_ocdid,
        reason=RejectedReason.UNKNOWN_JURISDICTION if in_state else RejectedReason.OUTSIDE_STATE,
    )
