"""One jurisdiction's uploaded rows against civicpatch's current roster: who matches whom."""

from shared.schemas import Person
from shared.utils.name_utils import build_canonical_map, nickname_tie, person_list_to_identities
from shared.utils.person_id_utils import resolve_person_id
from shared.utils.taxonomy import Taxonomy

from core.roster_comparison_fields import (
    compare_emails,
    compare_phones,
    compare_role,
    compare_start_date,
    compare_urls,
    role_ids,
)
from core.roster_comparison_warnings import row_warnings
from schemas.roster_comparisons import (
    Candidate,
    CandidateReason,
    ComparedField,
    FieldComparison,
    PersonComparison,
    PersonOutcome,
    UploadedRow,
)


def compare_people(
    rows: list[UploadedRow], roster: list[Person], taxonomy: Taxonomy
) -> list[PersonComparison]:
    """Every uploaded row once, then every roster person no row matched or named as a candidate.
    Sure matches claim their people first, so a guess never blocks one (the pipeline differs)."""
    identities = person_list_to_identities(roster)
    canonical_map = build_canonical_map(roster, identities)
    matches = [resolve_person_id(row.name, [], [], roster, canonical_map, identities) for row in rows]
    matched = _sure_matches(matches)
    people_by_id = {person.id: person for person in roster}
    matched_by_row = {person_id: rows[index].source_row for index, person_id in matched.items()}
    compared = [
        _with_warnings(
            row,
            _matched(row, people_by_id[matched[index]], taxonomy)
            if index in matched
            else _uncertain(row, row_matches, roster, matched_by_row),
            taxonomy,
        )
        for index, (row, row_matches) in enumerate(zip(rows, matches))
    ]
    accounted_for = {person_id for comparison in compared for person_id in _person_ids(comparison)}
    return compared + [
        PersonComparison(
            outcome=PersonOutcome.ONLY_IN_CIVICPATCH, person_id=person.id, person_name=person.name
        )
        for person in roster
        if person.id not in accounted_for
    ]


def civicpatch_role_ids(person: Person, taxonomy: Taxonomy) -> list[str]:
    """Each open membership's post role, plus the roles its label names (where extra roles live)."""
    ids = [
        role_id
        for membership in person.memberships
        for role_id in [membership.role_id, *role_ids(membership.label or "", taxonomy)]
    ]
    return list(dict.fromkeys(ids))


def _sure_matches(matches: list[list[Person]]) -> dict[int, str]:
    """Row index → person id, for rows with exactly one match; the first row claims a person."""
    claimed: dict[int, str] = {}
    for index, row_matches in enumerate(matches):
        if len(row_matches) == 1 and row_matches[0].id not in claimed.values():
            claimed[index] = row_matches[0].id
    return claimed


def _uncertain(
    row: UploadedRow,
    matches: list[Person],
    roster: list[Person],
    matched_by_row: dict[str, int],
) -> PersonComparison:
    """Several people the name fits, one another row took, or people only a nickname links."""
    if matches:
        reason, candidates = CandidateReason.SAME_NAME, matches
    else:
        reason, candidates = CandidateReason.NICKNAME, [p for p in roster if nickname_tie(row.name, p.name)]
    if not candidates:
        return PersonComparison(outcome=PersonOutcome.ONLY_IN_UPLOADED_DATA, uploaded=row)
    return _possible(row, [_candidate(p, reason, matched_by_row.get(p.id)) for p in candidates])


def _with_warnings(
    row: UploadedRow, comparison: PersonComparison, taxonomy: Taxonomy
) -> PersonComparison:
    warnings = row_warnings(row, comparison.candidates, taxonomy)
    return comparison.model_copy(update={"warnings": warnings})


def _person_ids(comparison: PersonComparison) -> set[str]:
    ids = [comparison.person_id, *(candidate.person_id for candidate in comparison.candidates)]
    return {person_id for person_id in ids if person_id}


def _matched(row: UploadedRow, person: Person, taxonomy: Taxonomy) -> PersonComparison:
    return PersonComparison(
        outcome=PersonOutcome.MATCHED,
        uploaded=row,
        person_id=person.id,
        person_name=person.name,
        fields=_fields(row, person, taxonomy),
    )


def _fields(row: UploadedRow, person: Person, taxonomy: Taxonomy) -> dict[ComparedField, FieldComparison]:
    return {
        ComparedField.ROLE: compare_role(row.role, civicpatch_role_ids(person, taxonomy), taxonomy),
        ComparedField.EMAILS: compare_emails(row.emails, person.emails),
        ComparedField.PHONES: compare_phones(row.phones, person.phones),
        ComparedField.URLS: compare_urls(row.urls, person.urls),
        ComparedField.START_DATE: compare_start_date(row.start_date, _earliest_start(person)),
    }


def _earliest_start(person: Person) -> str | None:
    dates = sorted(m.start_date for m in person.memberships if m.start_date)
    return dates[0] if dates else None


def _possible(row: UploadedRow, candidates: list[Candidate]) -> PersonComparison:
    return PersonComparison(outcome=PersonOutcome.POSSIBLE_MATCH, uploaded=row, candidates=candidates)


def _candidate(person: Person, reason: CandidateReason, already_matched_by_row: int | None) -> Candidate:
    return Candidate(
        person_id=person.id,
        name=person.name,
        reason=reason,
        already_matched_by_row=already_matched_by_row,
    )
