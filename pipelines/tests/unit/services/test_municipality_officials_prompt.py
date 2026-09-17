"""The officials prompt's organization scoping: what it names and lists.

Wording is judged by the evals; these pin what reaches the prompt at all.
"""

import pytest

from services.open_router.prompts import PromptOrganization, municipality_officials_prompt

pytestmark = pytest.mark.unit

_COUNCIL = PromptOrganization(name="City Council", posts=["Council Member District 1", "Council President"])


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

    assert "do not swap it for a" in prompt
    assert "Write each part exactly as the page writes it" in prompt

