"""The officials prompt's organization scoping: what it names and lists.

Wording is judged by the evals; these pin what reaches the prompt at all.
"""

import pytest

from services.open_router.prompts import PromptOrganization, municipality_officials_prompt

pytestmark = pytest.mark.unit

_COUNCIL = PromptOrganization(
    name="City Council", role_labels=["Council Member", "Council President"], divisions=["district 1"]
)
_COLD_COUNCIL = PromptOrganization(name="City Council", government_form_role_labels=["Council Member"])
_BARE_COUNCIL = PromptOrganization(name="City Council")


def _prompt(**kwargs) -> str:
    return municipality_officials_prompt([], current_date="2025-09-01", **kwargs)


def test_an_unscoped_prompt_names_no_body():
    prompt = _prompt()

    assert "TARGET BODY" not in prompt
    assert "prefer our word" not in prompt
    assert "usually has" not in prompt


def test_a_scoped_prompt_lists_its_roles_and_divisions_apart():
    prompt = _prompt(organization=_COUNCIL)

    assert "Only extract people who hold a post in City Council." in prompt
    assert "The roles in City Council, in our words:\n        - Council Member\n        - Council President" in prompt
    assert "Its divisions, in our words:\n        - district 1" in prompt


def test_a_scoped_prompt_prefers_known_roles_rather_than_dictating_them():
    prompt = _prompt(organization=_COUNCIL)

    assert "prefer our word" in prompt
    assert "copy each exactly" not in prompt


def test_a_scoped_prompt_still_explains_how_to_write_a_label_for_an_unlisted_role():
    prompt = _prompt(organization=_COUNCIL)

    assert "do not swap it for a" in prompt
    assert "Write each part exactly as the page writes it" in prompt


def test_a_cold_start_body_gets_its_forms_roles_as_a_guess():
    prompt = _prompt(organization=_COLD_COUNCIL)

    assert "A City Council usually has these roles:" in prompt
    assert "- Council Member" in prompt
    assert "not from this page" in prompt
    assert "prefer our word" not in prompt


def test_a_body_with_nothing_known_gets_only_the_page_rules():
    prompt = _prompt(organization=_BARE_COUNCIL)

    assert "Only extract people who hold a post in City Council." in prompt
    assert "usually has" not in prompt
    assert "prefer our word" not in prompt
    assert "Its divisions" not in prompt
    assert "Write each part exactly as the page writes it" in prompt


def test_an_unscoped_prompt_states_known_roles_and_divisions_and_only_suggests_the_forms():
    known = municipality_officials_prompt(
        ["Mayor", "Alderperson"], current_date="2025-09-01", divisions=["ward 1", "ward 2"]
    )
    guessed = municipality_officials_prompt(
        [], current_date="2025-09-01", government_form_role_labels=["Council Member", "Mayor"]
    )
    neither = municipality_officials_prompt([], current_date="2025-09-01")

    assert "Known elected roles for this municipality: Mayor, Alderperson." in known
    assert "Its divisions: ward 1, ward 2." in known
    assert "usually has these roles: Council Member, Mayor" in guessed
    assert "Known elected roles" not in guessed
    assert "usually has" not in neither and "Known elected roles" not in neither
