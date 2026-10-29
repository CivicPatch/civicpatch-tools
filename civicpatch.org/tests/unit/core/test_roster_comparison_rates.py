import pytest

from core.roster_comparison_rates import compared_organizations, rates, total
from schemas.roster_comparisons import (
    RunOrganization,
    ComparedField,
    FieldComparison,
    FieldLevel,
    PersonComparison,
    PersonOutcome,
    RowWarning,
    RowWarningCode,
)


def _emails(level: FieldLevel, uploaded: list[str], civicpatch: list[str]) -> PersonComparison:
    return PersonComparison(
        outcome=PersonOutcome.MATCHED,
        fields={ComparedField.EMAILS: FieldComparison(level=level, uploaded=uploaded, civicpatch=civicpatch)},
    )


_WARNING = RowWarning(code=RowWarningCode.INVALID_PHONE, message="'x' is not a phone number")

# Barre: three matched people, one only in civicpatch, one row with a warning.
BARRE = [
    _emails(FieldLevel.EQUAL, ["a"], ["a"]),
    _emails(FieldLevel.CIVICPATCH_HAS_MORE, ["b"], ["b", "c"]),
    _emails(FieldLevel.DIFFERS, ["d"], ["e"]),
    PersonComparison(outcome=PersonOutcome.ONLY_IN_CIVICPATCH, person_id="p"),
]
# Stowe: one matched person civicpatch has no email for, one possible match with a warning.
STOWE = [
    _emails(FieldLevel.CIVICPATCH_HAS_NONE, ["f"], []),
    PersonComparison(outcome=PersonOutcome.POSSIBLE_MATCH, warnings=[_WARNING]),
]


@pytest.mark.unit
def test_rates_count_outcomes_and_grade_fields_over_matched_people():
    barre = rates(BARRE)

    assert barre.outcomes.model_dump() == {
        "matched": 3, "possible_match": 0, "only_in_uploaded_data": 0, "only_in_civicpatch": 1,
        "only_in_civicpatch_not_compared": 0,
    }
    emails = barre.fields[ComparedField.EMAILS]
    assert (emails.agreement, emails.one_side_has_more, emails.conflict) == (2, 1, 1)
    assert (emails.uploaded_data_has_it, emails.civicpatch_has_it) == (3, 3)


@pytest.mark.unit
def test_a_state_total_adds_its_jurisdictions():
    state = total([rates(BARRE), rates(STOWE)])

    assert state.outcomes.matched == 4
    assert state.outcomes.possible_match == 1
    assert state.rows_with_warnings == 1
    emails = state.fields[ComparedField.EMAILS]
    assert (emails.agreement, emails.conflict) == (2, 1)
    assert (emails.uploaded_data_has_it, emails.civicpatch_has_it) == (4, 3)


@pytest.mark.unit
def test_a_person_conflicting_in_two_fields_is_one_person_with_conflicts():
    differs = FieldComparison(level=FieldLevel.DIFFERS, uploaded=["x"], civicpatch=["y"])
    both = PersonComparison(
        outcome=PersonOutcome.MATCHED, fields={ComparedField.EMAILS: differs, ComparedField.PHONES: differs}
    )

    counted = total([rates([both]), rates(BARRE)])

    assert counted.fields[ComparedField.EMAILS].conflict + counted.fields[ComparedField.PHONES].conflict == 3
    assert counted.people_with_conflicts == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    ("asked", "compared"),
    [(None, ["Selectboard"]), (["Board of Listers"], ["Board of Listers"])],
)
def test_the_compared_organizations_are_the_asked_else_the_matched(asked, compared):
    organizations = [
        RunOrganization(name="Selectboard", jurisdictions=2, matched=5, civicpatch_people=9),
        RunOrganization(name="Board of Listers", jurisdictions=2, matched=0, civicpatch_people=6),
    ]

    assert compared_organizations(asked, organizations) == compared


@pytest.mark.unit
def test_every_field_has_counts_even_when_nothing_was_matched():
    nobody = rates([PersonComparison(outcome=PersonOutcome.ONLY_IN_CIVICPATCH, person_id="p")])

    assert set(nobody.fields) == set(ComparedField)
    assert nobody.fields[ComparedField.ROLE].agreement == 0
