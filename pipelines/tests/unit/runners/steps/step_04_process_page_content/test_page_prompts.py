"""A page's verdict may be reused only while everything the LLM saw besides the text is the same."""

import pytest
from runners.people_collector.steps.step_04_process_page_content.page_prompts import (
    prompt_hash,
)
from shared.schemas import GovernmentForm, KnownOrganization, PipelineRunConfig, Post

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_URL = "https://seattle.gov/council"
_ROLES = ["Mayor", "Council Member"]
_CONFIG = PipelineRunConfig(url="https://seattle.gov", name="Seattle")


def _organization(organization_id: str, name: str, labels: list[str]) -> KnownOrganization:
    posts = [
        Post(
            id=f"{organization_id}-{label}",
            jurisdiction_ocdid=_OCDID,
            organization_id=organization_id,
            role_id="role",
            division_ocdid="ocd-division/country:us/state:wa/place:seattle",
            label=label,
        )
        for label in labels
    ]
    return KnownOrganization(id=organization_id, name=name, posts=posts)


_COUNCIL = _organization("council", "City Council", ["Council Member District 1"])
_MAYOR = _organization("mayor", "Office of the Mayor", ["Mayor"])


def _hash(
    url: str = _URL,
    config: PipelineRunConfig = _CONFIG,
    roles: list[str] = _ROLES,
    organizations: list[KnownOrganization] = [_COUNCIL, _MAYOR],
) -> str:
    return prompt_hash(url, config, _OCDID, roles, organizations)


def test_the_same_inputs_give_the_same_hash():
    assert _hash() == _hash()


def test_a_government_form_change_moves_it():
    """The input the 09-18 hand-listed design would have missed."""
    changed = _CONFIG.model_copy(update={"government_form": GovernmentForm.COUNCIL_MANAGER})

    assert _hash(config=changed) != _hash()


def test_a_renamed_organization_moves_it():
    renamed = _organization("council", "Seattle City Council", ["Council Member District 1"])

    assert _hash(organizations=[renamed, _MAYOR]) != _hash()


def test_an_edited_post_label_moves_it():
    relabelled = _organization("council", "City Council", ["Councilmember, District 1"])

    assert _hash(organizations=[relabelled, _MAYOR]) != _hash()


def test_a_new_known_role_moves_it():
    assert _hash(roles=[*_ROLES, "City Attorney"]) != _hash()


def test_each_page_has_its_own():
    """The relevance prompt names the page, so reuse only ever compares a url with itself."""
    assert _hash(url="https://seattle.gov/mayor") != _hash()
