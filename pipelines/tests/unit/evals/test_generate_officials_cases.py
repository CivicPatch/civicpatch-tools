"""Which draft officials cases the generator proposes, and who it expects in each."""

import pytest
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from tests.prompts.tests.evals.generate_officials_cases import (
    CandidateCase,
    PublishedPerson,
    Variant,
    _plausible,
    a_variety,
    people_in,
)

pytestmark = pytest.mark.unit

_PAGE = "https://millburyma.gov/1506/board-of-selectmen"
_SELECT_BOARD = DerivedOrganization(name="Select Board", role_labels=["Select Board Member", "Chair"])
_TOWN_MEETING = DerivedOrganization(name="Town Meeting", role_labels=["Moderator"])
_FORM = [_SELECT_BOARD, _TOWN_MEETING]


def _person(name: str, *roles: str) -> PublishedPerson:
    return PublishedPerson(name=name, role_names=list(roles), source_urls=[_PAGE])


def test_a_role_no_organization_lists_goes_to_the_main_board():
    people = [_person("Nicholas Lazzaro", "Clerk"), _person("Mary Krumsiek", "Chair")]

    assert [person.name for person in people_in(_SELECT_BOARD, _FORM, people, _PAGE)] == [
        "Nicholas Lazzaro",
        "Mary Krumsiek",
    ]
    assert people_in(_TOWN_MEETING, _FORM, people, _PAGE) == []


def test_a_person_is_filed_only_with_the_roles_that_body_holds():
    people = [_person("Pat Moderator", "Moderator", "Select Board Member")]

    [in_town_meeting] = people_in(_TOWN_MEETING, _FORM, people, _PAGE)

    assert in_town_meeting.role_names == ["Moderator"]


def test_someone_the_page_does_not_cite_is_not_expected():
    elsewhere = PublishedPerson(name="Elsewhere", role_names=["Chair"], source_urls=["https://x.gov/other"])

    assert people_in(_SELECT_BOARD, _FORM, [elsewhere], _PAGE) == []


def test_a_town_meeting_is_tried_only_where_the_state_config_lists_it():
    listed = {GovernmentForm.OPEN_TOWN_MEETING: object()}

    assert _plausible(GovernmentForm.OPEN_TOWN_MEETING, "Millbury town", listed) is True
    assert _plausible(GovernmentForm.OPEN_TOWN_MEETING, "Adamsville town", {}) is False
    assert _plausible(GovernmentForm.MAYOR_COUNCIL, "Seattle city", {}) is True
    assert _plausible(GovernmentForm.MAYOR_COUNCIL, "Millbury town", {}) is False


def _cases(form: GovernmentForm, run: str) -> list[CandidateCase]:
    return [
        CandidateCase(
            case_id=f"{run}_{variant.value}",
            input_path="input.md",
            government_form=form,
            form_was_decided=False,
            organization=_SELECT_BOARD,
            variant=variant,
            known_titles=[],
            people=[],
        )
        for variant in Variant
    ]


def test_one_state_cannot_fill_a_form():
    chosen = a_variety(
        [
            ("tx", _cases(GovernmentForm.MAYOR_COUNCIL, "abernathy")),
            ("tx", _cases(GovernmentForm.MAYOR_COUNCIL, "abilene")),
            ("ca", _cases(GovernmentForm.MAYOR_COUNCIL, "amador")),
        ]
    )

    assert sorted({case.case_id.split("_")[0] for case in chosen}) == ["abernathy", "amador"]
