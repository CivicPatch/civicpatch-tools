"""A whole upload into one run: rows grouped by jurisdiction, each compared."""

from shared.schemas import Person
from shared.utils.taxonomy import Taxonomy

from core.roster_comparison import compare_people
from core.roster_comparison_rates import rates, total
from schemas.roster_comparisons import (
    JurisdictionComparison,
    PersonComparison,
    ResolvedUpload,
    RosterComparison,
    UploadedRow,
)


def build_comparison(
    upload: ResolvedUpload,
    state_ocdids: set[str],
    rosters: dict[str, list[Person]],
    taxonomy: Taxonomy,
    organization_names: dict[str, str],
) -> RosterComparison:
    """`state_ocdids` are the state's jurisdictions at the upload's level; `rosters` holds the people
    with an open membership in those the upload names."""
    rows_by_ocdid = _rows_by_ocdid(upload.rows)
    jurisdictions = [
        _jurisdiction(ocdid, rows, rosters.get(ocdid, []), taxonomy, organization_names)
        for ocdid, rows in rows_by_ocdid.items()
    ]
    return RosterComparison(
        state=upload.state,
        level=upload.level,
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
    ocdid: str,
    rows: list[UploadedRow],
    roster: list[Person],
    taxonomy: Taxonomy,
    organization_names: dict[str, str],
) -> JurisdictionComparison:
    people = _with_organizations(compare_people(rows, roster, taxonomy), roster, organization_names)
    return JurisdictionComparison(jurisdiction_ocdid=ocdid, rates=rates(people), people=people)


def _with_organizations(
    people: list[PersonComparison], roster: list[Person], organization_names: dict[str, str]
) -> list[PersonComparison]:
    """Each compared civicpatch person's organizations, by name."""
    roster_by_id = {person.id: person for person in roster}
    return [
        comparison.model_copy(
            update={"organizations": _organizations(roster_by_id[comparison.person_id], organization_names)}
        )
        if comparison.person_id in roster_by_id
        else comparison
        for comparison in people
    ]


def _organizations(person: Person, organization_names: dict[str, str]) -> list[str]:
    ids = [membership.organization_id for membership in person.memberships]
    return list(dict.fromkeys(organization_names[id_] for id_ in ids if id_ in organization_names))
