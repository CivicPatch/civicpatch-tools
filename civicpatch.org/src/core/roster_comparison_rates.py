"""Counts over compared people, per jurisdiction and summed per state. Counts, not percentages:
they add up across jurisdictions, and a percentage is derived where it is shown."""

from collections import Counter

from schemas.roster_comparisons import (
    ComparedField,
    ComparisonRates,
    FieldComparison,
    FieldCounts,
    FieldFilter,
    FieldLevel,
    JurisdictionRates,
    OutcomeCounts,
    PersonComparison,
    PersonOutcome,
)

ONE_SIDE_HAS_MORE = frozenset(
    {FieldLevel.CIVICPATCH_HAS_MORE, FieldLevel.UPLOADED_DATA_HAS_MORE, FieldLevel.OVERLAP}
)
AGREEMENT = ONE_SIDE_HAS_MORE | {FieldLevel.EQUAL}
LEVELS_BY_FILTER = {
    FieldFilter.CONFLICT: [FieldLevel.DIFFERS],
    FieldFilter.ONE_SIDE_HAS_MORE: sorted(ONE_SIDE_HAS_MORE),
}


def rates(people: list[PersonComparison]) -> ComparisonRates:
    outcomes = Counter(person.outcome for person in people)
    matched = [person for person in people if person.outcome is PersonOutcome.MATCHED]
    return ComparisonRates(
        outcomes=OutcomeCounts(**{outcome.value: outcomes[outcome] for outcome in PersonOutcome}),
        fields={
            field: _field_counts([person.fields[field] for person in matched if field in person.fields])
            for field in ComparedField
        },
        rows_with_warnings=sum(1 for person in people if person.warnings),
    )


def total(parts: list[ComparisonRates]) -> ComparisonRates:
    """A state's counts: each jurisdiction's, added."""
    return ComparisonRates(
        outcomes=OutcomeCounts(**_summed([part.outcomes.model_dump() for part in parts])),
        fields={
            field: FieldCounts(
                **_summed([part.fields[field].model_dump() for part in parts if field in part.fields])
            )
            for field in ComparedField
        },
        rows_with_warnings=sum(part.rows_with_warnings for part in parts),
    )


def worst_first(jurisdictions: list[JurisdictionRates]) -> list[JurisdictionRates]:
    """Most people not plainly matched first, then most warnings; ties by ocdid."""
    return sorted(
        jurisdictions,
        key=lambda j: (-_unmatched(j.rates.outcomes), -j.rates.rows_with_warnings, j.jurisdiction_ocdid),
    )


def _unmatched(outcomes: OutcomeCounts) -> int:
    return outcomes.possible_match + outcomes.only_in_uploaded_data + outcomes.only_in_civicpatch


def _field_counts(comparisons: list[FieldComparison]) -> FieldCounts:
    return FieldCounts(
        agreement=sum(1 for c in comparisons if c.level in AGREEMENT),
        one_side_has_more=sum(1 for c in comparisons if c.level in ONE_SIDE_HAS_MORE),
        conflict=sum(1 for c in comparisons if c.level is FieldLevel.DIFFERS),
        unknown=sum(1 for c in comparisons if c.level is FieldLevel.UNKNOWN),
        uploaded_data_has_it=sum(1 for c in comparisons if c.uploaded),
        civicpatch_has_it=sum(1 for c in comparisons if c.civicpatch),
    )


def _summed(counts: list[dict[str, int]]) -> dict[str, int]:
    summed: Counter[str] = Counter()
    for count in counts:
        summed.update(count)
    return dict(summed)
