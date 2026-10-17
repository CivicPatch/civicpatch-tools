"""The officials prompt's organization scoping: what it names and lists.

Wording is judged by the evals; these pin what reaches the prompt at all.
"""

import pytest

from services.open_router.prompts import PromptOrganization, elected_officials_prompt

pytestmark = pytest.mark.unit

_COUNCIL = PromptOrganization(
    name="City Council", role_labels=["Council Member", "Council President"], divisions=["district 1"]
)
_COLD_COUNCIL = PromptOrganization(name="City Council", government_form_role_labels=["Council Member"])
_BARE_COUNCIL = PromptOrganization(name="City Council")


def _prompt(**kwargs) -> str:
    return elected_officials_prompt([], current_date="2025-09-01", **kwargs)


def test_a_term_that_ended_before_the_current_date_is_left_out():
    prompt = _prompt()

    assert "Current Date: 2025-09-01" in prompt
    assert "gives a term that ended before the current date: leave those people out" in prompt


def test_an_unscoped_prompt_names_no_body_and_lists_no_roles():
    prompt = _prompt()

    assert "TARGET BODY" not in prompt
    assert "Roles" not in prompt


def test_a_scoped_prompt_lists_its_roles_and_divisions():
    prompt = _prompt(organization=_COUNCIL)

    assert "Only extract people who hold a post in City Council." in prompt
    assert "- Roles in City Council:\n        - Council Member\n        - Council President" in prompt
    assert "- Divisions in City Council:\n        - district 1" in prompt
    assert "usually has" not in prompt


def test_a_cold_start_body_lists_the_roles_its_form_usually_has():
    prompt = _prompt(organization=_COLD_COUNCIL)

    assert "- Roles a City Council usually has:\n        - Council Member" in prompt
    assert "Roles in City Council" not in prompt


def test_a_body_with_nothing_known_lists_nothing():
    prompt = _prompt(organization=_BARE_COUNCIL)

    assert "Only extract people who hold a post in City Council." in prompt
    assert "Roles" not in prompt
    assert "Divisions" not in prompt
    assert "Write each part exactly as the page writes it" in prompt


def test_every_office_a_person_holds_goes_in_one_label():
    prompt = _prompt(organization=_COUNCIL)

    assert "include every one in the same label" in prompt
    assert "presiding title" not in prompt


def test_an_unscoped_prompt_lists_known_roles_and_divisions_or_the_forms_usual_roles():
    known = elected_officials_prompt(
        ["Mayor", "Alderperson"], current_date="2025-09-01", divisions=["ward 1", "ward 2"]
    )
    guessed = elected_officials_prompt(
        [], current_date="2025-09-01", government_form_role_labels=["Council Member", "Mayor"]
    )
    neither = elected_officials_prompt([], current_date="2025-09-01")

    assert "- Roles in this municipality: Mayor, Alderperson." in known
    assert "- Divisions in this municipality: ward 1, ward 2." in known
    assert "- Roles this municipality usually has: Council Member, Mayor." in guessed
    assert "Roles in this municipality" not in guessed
    assert "Roles" not in neither
