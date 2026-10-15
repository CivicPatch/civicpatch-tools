"""Which draft officials cases the generator proposes, and who it expects in each."""

import pytest
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.government_forms import DerivedOrganization
from tests.prompts.tests.evals.generate_officials_cases import (
    CandidateCase,
    PublishedPerson,
    Variant,
    _plausible,
    a_variety,
    case_id,
    people_in,
    prompt_inputs,
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
    local = JurisdictionLevel.LOCAL

    assert _plausible(GovernmentForm.OPEN_TOWN_MEETING, "Millbury town", listed, local) is True
    assert _plausible(GovernmentForm.OPEN_TOWN_MEETING, "Adamsville town", {}, local) is False
    assert _plausible(GovernmentForm.MAYOR_COUNCIL, "Seattle city", {}, local) is True
    assert _plausible(GovernmentForm.MAYOR_COUNCIL, "Millbury town", {}, local) is False
    assert _plausible(GovernmentForm.TOWNSHIP_BOARD, "Ada township", {}, local) is True
    assert _plausible(GovernmentForm.TOWNSHIP_BOARD, "Belle Meade city", {}, local) is False
    assert _plausible(GovernmentForm.TOWNSHIP_BOARD, "Armada village", {}, local) is True
    assert _plausible(GovernmentForm.MAYOR_COUNCIL, "Gibbsboro borough", {}, local) is True
    assert _plausible(GovernmentForm.COUNCIL_MANAGER, "Gibbsboro borough", {}, local) is False


def test_a_county_may_have_any_form_its_state_allows():
    counties = JurisdictionLevel.COUNTIES

    assert _plausible(GovernmentForm.COUNTY_EXECUTIVE, "King County", {}, counties) is True
    assert _plausible(GovernmentForm.COMMISSION, "King County", {}, counties) is True


def _case(form: GovernmentForm, run: str, variant: Variant, scoped: bool = True) -> CandidateCase:
    return CandidateCase(
        case_id=f"{run}_{variant.value}",
        input_path="input.md",
        government_form=form,
        form_was_decided=False,
        organization=_SELECT_BOARD,
        scoped=scoped,
        variant=variant,
        current_date="2026-09-25",
        role_labels=["Select Board Member", "Chair"],
        divisions=["ward 1"],
        people=[],
    )


def _cases(form: GovernmentForm, run: str) -> list[CandidateCase]:
    return [_case(form, run, variant) for variant in Variant]


def test_a_scoped_case_names_its_body_and_an_unscoped_one_lists_known_roles():
    scoped = _case(GovernmentForm.OPEN_TOWN_MEETING, "millbury", Variant.KNOWN_TITLES)
    unscoped = _case(GovernmentForm.COUNCIL_MANAGER, "ada", Variant.KNOWN_TITLES, scoped=False)

    assert prompt_inputs(scoped) == {
        "organization": {"name": "Select Board", "role_labels": ["Select Board Member", "Chair"], "divisions": ["ward 1"]}
    }
    assert prompt_inputs(unscoped) == {"known_roles": ["Select Board Member", "Chair"], "divisions": ["ward 1"]}


def test_an_unscoped_case_carries_the_weak_suggestion_apart_and_nothing_for_none():
    suggested = _case(GovernmentForm.COUNCIL_MANAGER, "ada", Variant.SUGGESTED_TITLES, scoped=False)
    none = _case(GovernmentForm.COUNCIL_MANAGER, "ada", Variant.NO_TITLES, scoped=False)

    assert prompt_inputs(suggested) == {"government_form_role_labels": ["Select Board Member", "Chair"]}
    assert prompt_inputs(none) == {}


def test_one_state_cannot_fill_a_form():
    chosen = a_variety(
        [
            ("tx", _cases(GovernmentForm.MAYOR_COUNCIL, "abernathy")),
            ("tx", _cases(GovernmentForm.MAYOR_COUNCIL, "abilene")),
            ("ca", _cases(GovernmentForm.MAYOR_COUNCIL, "amador")),
        ]
    )

    assert sorted({case.case_id.split("_")[0] for case in chosen}) == ["abernathy", "amador"]


def test_an_unscoped_run_shares_its_known_and_no_titles_cases_across_forms():
    known = Variant.KNOWN_TITLES
    suggested = Variant.SUGGESTED_TITLES

    assert case_id("place_ada", GovernmentForm.COUNCIL_MANAGER, "Council", known, False) == case_id(
        "place_ada", GovernmentForm.COMMISSION, "Commission", known, False
    )
    assert case_id("place_ada", GovernmentForm.COUNCIL_MANAGER, "Council", suggested, False) != case_id(
        "place_ada", GovernmentForm.COMMISSION, "Commission", suggested, False
    )
    assert case_id("place_x", GovernmentForm.MAYOR_COUNCIL, "Council", known, True) != case_id(
        "place_x", GovernmentForm.MAYOR_COUNCIL, "Office of the Mayor", known, True
    )
