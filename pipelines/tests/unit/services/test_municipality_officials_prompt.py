"""The officials prompt's organization scoping: what it names, lists and excludes.

Wording is judged by the evals; these pin what reaches the prompt at all.
"""

import pytest

from services.open_router.prompts import PromptOrganization, municipality_officials_prompt

pytestmark = pytest.mark.unit

_COUNCIL = PromptOrganization(name="City Council", posts=["Council Member District 1", "Council President"])
_MAYOR = PromptOrganization(name="Office of the Mayor", posts=["Mayor"])


def _prompt(**kwargs) -> str:
    return municipality_officials_prompt([], current_date="2025-09-01", **kwargs)


def test_an_unscoped_prompt_names_no_body():
    prompt = _prompt()

    assert "TARGET BODY" not in prompt
    assert "copy it exactly" not in prompt


def test_a_scoped_prompt_names_its_body_and_lists_its_posts_to_pick_from():
    prompt = _prompt(organization=_COUNCIL)

    assert "Only extract people who hold a post in City Council." in prompt
    assert "- Council Member District 1" in prompt
    assert "- Council President" in prompt


def test_a_scoped_prompt_still_explains_how_to_write_a_label_for_an_unlisted_post():
    prompt = _prompt(organization=_COUNCIL)

    assert "not listed, do not pick" in prompt
    assert "Write each part exactly as the page writes it" in prompt


def test_other_bodies_are_excluded_with_their_posts_when_given():
    prompt = _prompt(organization=_COUNCIL, other_organizations=[_MAYOR])

    assert "- Office of the Mayor: Mayor" in prompt


def test_other_bodies_given_without_posts_are_excluded_by_name_only():
    prompt = _prompt(organization=_COUNCIL, other_organizations=[PromptOrganization(name="Office of the Mayor")])

    assert "- Office of the Mayor\n" in prompt


def test_no_other_bodies_means_no_exclusion_block():
    assert "belong to other bodies" not in _prompt(organization=_COUNCIL)
