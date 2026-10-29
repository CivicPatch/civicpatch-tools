"""The officials prompt: what it names and lists, and the organizations it offers to pick from.

Wording is judged by the evals; these pin what reaches the prompt at all.
"""

import pytest

from services.open_router.prompts import elected_officials_prompt
from shared.schemas import JurisdictionLevel

pytestmark = pytest.mark.unit

_LOCAL = JurisdictionLevel.LOCAL



def _prompt(**kwargs) -> str:
    return elected_officials_prompt([], level=kwargs.pop("level", _LOCAL), current_date="2025-09-01", **kwargs)


def test_a_county_is_named_as_the_target_and_in_the_jurisdiction_line():
    prompt = _prompt(level=JurisdictionLevel.COUNTIES, state="tx", county="travis")

    assert "serving officials of the target county" in prompt
    assert "any general\n      county contact" in prompt
    assert "Jurisdiction: travis County, tx" in prompt
    assert "municipal" not in prompt


def test_a_town_inside_a_county_is_not_read_as_the_county():
    prompt = _prompt(state="nj", county="bergen")

    assert "serving officials of the target municipality" in prompt
    assert "any general\n      municipal contact" in prompt
    assert "Jurisdiction: a municipality in bergen County, nj" in prompt


def test_a_town_directly_under_its_state_names_only_the_state():
    assert "Jurisdiction: ca\n" in _prompt(state="ca")


def test_a_term_that_ended_before_the_current_date_is_left_out():
    prompt = _prompt()

    assert "Current Date: 2025-09-01" in prompt
    assert "gives a term that ended before the current date: leave those people out" in prompt


def test_an_unscoped_prompt_names_no_body_and_lists_no_roles():
    prompt = _prompt()

    assert "TARGET BODY" not in prompt
    assert "Roles" not in prompt


def test_every_office_a_person_holds_goes_in_one_label():
    prompt = _prompt()

    assert "include every one in the same label" in prompt
    assert "presiding title" not in prompt


def test_the_prompt_lists_known_roles_and_divisions_and_the_forms_usual_roles():
    known = elected_officials_prompt(
        ["Mayor", "Alderperson"], level=_LOCAL, current_date="2025-09-01", divisions=["ward 1", "ward 2"]
    )
    guessed = elected_officials_prompt(
        [], level=_LOCAL, current_date="2025-09-01", government_form_role_labels=["Council Member", "Mayor"]
    )
    both = elected_officials_prompt(
        ["Select Board Member"], level=_LOCAL, current_date="2025-09-01", government_form_role_labels=["Town Clerk"]
    )
    neither = elected_officials_prompt([], level=_LOCAL, current_date="2025-09-01")

    assert "- Roles in this municipality: Mayor, Alderperson." in known
    assert "- Divisions in this municipality: ward 1, ward 2." in known
    assert "- Roles the law provides for (this municipality may fill fewer): Council Member, Mayor." in guessed
    assert "Roles in this municipality" not in guessed
    assert "- Roles in this municipality: Select Board Member." in both
    assert "- Roles the law provides for (this municipality may fill fewer): Town Clerk." in both
    assert "Roles" not in neither


def test_the_organization_is_copied_as_written_with_ours_listed_for_reference():
    prompt = _prompt(organization_choices=["Selectboard", "Board of Listers"])

    assert "copied exactly as the\n      page writes it" in prompt
    assert '- "Selectboard"' in prompt and '- "Board of Listers"' in prompt
    assert "chosen from this list only" not in prompt


def test_with_nothing_to_pick_from_the_prompt_asks_for_no_organization():
    assert "organization:" not in _prompt()


def test_the_governing_body_and_the_listed_offices_are_the_only_ways_in():
    roles = _prompt(government_form_role_labels=["Town Clerk"])
    organizations = _prompt(organization_choices=["Selectboard"])
    both = _prompt(government_form_role_labels=["Town Clerk"], organization_choices=["Selectboard"])

    assert "Extract a person only if:\n    - they are a member of the governing body" in roles
    assert "their title is one of the roles listed under label below" in roles
    assert "listed under organization" not in roles
    assert "they hold a seat on one of the bodies listed under organization" in organizations
    assert "roles listed under label" not in organizations
    assert "roles listed under label" in both and "listed under organization" in both
    assert "Anyone else stays out, elected or not: a title on no list" in both
    assert "elected" not in both.split("Anyone else stays out, elected or not")[0].split("not person names.")[1]


def test_with_nothing_listed_only_the_governing_body_is_in():
    prompt = _prompt()

    assert "Extract a person only if:\n    - they are a member of the governing body (e.g. Mayor, City Council, Board of Aldermen,\n      Board of Commissioners).\n" in prompt
    assert "listed under label" not in prompt and "listed under organization" not in prompt
    assert "a clerk or manager not listed" in prompt
