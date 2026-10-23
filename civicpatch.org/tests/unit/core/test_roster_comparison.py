import pytest
from shared.schemas import Membership, Person, Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison import civicpatch_role_ids, compare_people
from schemas.roster_comparisons import (
    CandidateReason,
    ComparedField,
    FieldLevel,
    PersonOutcome,
    RowWarningCode,
    UploadedRow,
)

_JURISDICTION = "ocd-jurisdiction/country:us/state:vt/place:barre/government"
_DIVISION = "ocd-division/country:us/state:vt/place:barre"

# As open-data's config.yml has it: council posts are the one `member` role.
TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="vice-mayor", label="Vice Mayor", is_unique=True),
            Role(id="member", label="Member", aliases=["Council Member"]),
        ]
    )
)


def _person(person_id: str, name: str, *, emails=(), label: str | None = None) -> Person:
    return Person(
        id=person_id,
        name=name,
        emails=list(emails),
        jurisdiction_ocdid=_JURISDICTION,
        memberships=[
            Membership(
                post_id=f"post-{person_id}",
                role_id="member",
                role_label="Member",
                division_ocdid=_DIVISION,
                label=label,
            )
        ],
    )


def _row(name: str, source_row: int = 2, **fields) -> UploadedRow:
    return UploadedRow(source_row=source_row, jurisdiction_ocdid=_JURISDICTION, name=name, **fields)


def _by_outcome(comparisons, outcome: PersonOutcome):
    return [comparison for comparison in comparisons if comparison.outcome is outcome]


@pytest.mark.unit
def test_a_nickname_only_one_person_fits_is_a_possible_match_not_a_match():
    roster = [_person("robert", "Robert Smith"), _person("roberta", "Roberta Smith")]

    [bob, roberta] = compare_people([_row("Bob Smith")], roster, TAXONOMY)

    assert bob.outcome is PersonOutcome.POSSIBLE_MATCH
    assert [(c.person_id, c.reason) for c in bob.candidates] == [("robert", CandidateReason.NICKNAME)]
    assert (roberta.outcome, roberta.person_id) == (PersonOutcome.ONLY_IN_CIVICPATCH, "roberta")


@pytest.mark.unit
def test_a_nickname_guess_never_blocks_another_rows_exact_match():
    roster = [_person("robert", "Robert Smith"), _person("roberta", "Roberta Smith")]

    bob, robert, roberta = compare_people(
        [_row("Bob Smith", 5), _row("Robert Smith", 6)], roster, TAXONOMY
    )

    assert (robert.outcome, robert.person_id) == (PersonOutcome.MATCHED, "robert")
    assert bob.outcome is PersonOutcome.POSSIBLE_MATCH
    assert [(c.person_id, c.already_matched_by_row) for c in bob.candidates] == [("robert", 6)]
    assert [w.code for w in bob.warnings] == [RowWarningCode.CANDIDATE_ALREADY_MATCHED]
    assert (roberta.outcome, roberta.person_id) == (PersonOutcome.ONLY_IN_CIVICPATCH, "roberta")


@pytest.mark.unit
def test_a_nickname_two_people_fit_lists_both_and_neither_is_only_in_civicpatch():
    roster = [_person("robert", "Robert Smith"), _person("william", "William Smith")]

    comparisons = compare_people([_row("Bill Smith")], roster, TAXONOMY)

    assert len(comparisons) == 1
    assert {c.person_id for c in comparisons[0].candidates} == {"robert", "william"}
    assert {c.reason for c in comparisons[0].candidates} == {CandidateReason.NICKNAME}


@pytest.mark.unit
def test_a_name_two_people_share_is_a_possible_match_with_both():
    roster = [_person("a", "John Smith"), _person("b", "John Smith")]

    [comparison] = compare_people([_row("John Smith")], roster, TAXONOMY)

    assert comparison.outcome is PersonOutcome.POSSIBLE_MATCH
    assert {(c.person_id, c.reason) for c in comparison.candidates} == {
        ("a", CandidateReason.SAME_NAME),
        ("b", CandidateReason.SAME_NAME),
    }


@pytest.mark.unit
def test_a_match_grades_its_fields():
    roster = [_person("jane", "Jane Doe", emails=["jdoe@barre.gov"])]

    [jane] = compare_people([_row("Jane Doe", emails=["jane@gmail.com"], role="Council Member")], roster, TAXONOMY)

    assert (jane.outcome, jane.person_id) == (PersonOutcome.MATCHED, "jane")
    assert jane.fields[ComparedField.EMAILS].level is FieldLevel.DIFFERS
    assert jane.fields[ComparedField.ROLE].level is FieldLevel.EQUAL
    assert jane.fields[ComparedField.PHONES].level is FieldLevel.BOTH_EMPTY


@pytest.mark.unit
def test_an_extra_role_in_the_membership_label_counts_as_one_civicpatch_holds():
    roster = [_person("tom", "Tom Reyes", label="Vice Mayor")]

    [tom] = compare_people([_row("Tom Reyes", role="Vice Mayor")], roster, TAXONOMY)

    assert civicpatch_role_ids(roster[0], TAXONOMY) == ["member", "vice-mayor"]
    assert tom.fields[ComparedField.ROLE].level is FieldLevel.CIVICPATCH_HAS_MORE


@pytest.mark.unit
def test_rows_and_people_with_no_link_land_on_their_own_sides():
    roster = [_person("maria", "Maria Ortiz")]

    comparisons = compare_people([_row("Pat Lin", source_row=9)], roster, TAXONOMY)

    [pat] = _by_outcome(comparisons, PersonOutcome.ONLY_IN_UPLOADED_DATA)
    [maria] = _by_outcome(comparisons, PersonOutcome.ONLY_IN_CIVICPATCH)
    assert pat.uploaded is not None and pat.uploaded.source_row == 9
    assert maria.person_id == "maria"


@pytest.mark.unit
def test_the_same_person_listed_twice_is_a_match_then_a_possible_match():
    roster = [_person("jane", "Jane Doe")]

    first, second = compare_people([_row("Jane Doe", 2), _row("Jane Doe", 3)], roster, TAXONOMY)

    assert first.outcome is PersonOutcome.MATCHED
    assert second.outcome is PersonOutcome.POSSIBLE_MATCH
    assert [c.person_id for c in second.candidates] == ["jane"]
