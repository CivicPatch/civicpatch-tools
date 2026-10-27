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

    assert "elected officials of the target county" in prompt
    assert "any general\n      county contact" in prompt
    assert "Jurisdiction: travis County, tx" in prompt
    assert "municipal" not in prompt


def test_a_town_inside_a_county_is_not_read_as_the_county():
    prompt = _prompt(state="nj", county="bergen")

    assert "elected officials of the target municipality" in prompt
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


def test_an_unscoped_prompt_lists_known_roles_and_divisions_or_the_forms_usual_roles():
    known = elected_officials_prompt(
        ["Mayor", "Alderperson"], level=_LOCAL, current_date="2025-09-01", divisions=["ward 1", "ward 2"]
    )
    guessed = elected_officials_prompt(
        [], level=_LOCAL, current_date="2025-09-01", government_form_role_labels=["Council Member", "Mayor"]
    )
    neither = elected_officials_prompt([], level=_LOCAL, current_date="2025-09-01")

    assert "- Roles in this municipality: Mayor, Alderperson." in known
    assert "- Divisions in this municipality: ward 1, ward 2." in known
    assert "- Roles this municipality usually has: Council Member, Mayor." in guessed
    assert "Roles in this municipality" not in guessed
    assert "Roles" not in neither


def test_the_organizations_to_pick_from_are_listed_with_none():
    prompt = _prompt(organization_choices=["Selectboard", "Board of Listers"])

    assert "chosen from this list only" in prompt
    assert '- "Selectboard"' in prompt and '- "Board of Listers"' in prompt
    assert '"none" when the person holds no post in any body on the list' in prompt


def test_with_nothing_to_pick_from_the_prompt_asks_for_no_organization():
    assert "organization:" not in _prompt()
