"""The coverage prompt's roles and divisions: known as fact, a cold start's form roles as a guess,
nothing when there is neither. Wording is judged by the evals."""

import pytest

from services.open_router.prompts import page_covers_organization_prompt

pytestmark = pytest.mark.unit


def test_known_roles_and_divisions_are_listed_apart():
    prompt = page_covers_organization_prompt("City Council", ["Council Member"], divisions=["district 1"])

    assert "Roles in it:\n      - Council Member" in prompt
    assert "Its divisions:\n      - district 1" in prompt
    assert "usually has" not in prompt


def test_a_cold_start_lists_its_forms_roles_as_a_guess():
    prompt = page_covers_organization_prompt(
        "Select Board", [], government_form_role_labels=["Select Board Member"]
    )

    assert "Roles it usually has (a guess from its form of government, not from this page):" in prompt
    assert "- Select Board Member" in prompt
    assert "Roles in it:" not in prompt


def test_nothing_known_lists_nothing_and_does_not_point_at_a_list():
    prompt = page_covers_organization_prompt("Town Meeting", [])

    assert "Roles" not in prompt
    assert "Its divisions" not in prompt
    assert "listed above" not in prompt
    assert "whatever the page calls their office" in prompt
