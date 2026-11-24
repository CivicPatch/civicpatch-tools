"""A page's verdict may be reused only while everything the LLM saw besides the text is the same."""

from datetime import datetime

import pytest
import services.open_router.prompts as open_router_prompts
from runners.pipeline03_people_collector.schemas import ExpectedMembership
from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content import page_prompts
from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content.page_prompts import (
    page_extraction_prompt,
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
            role_label=label,
        )
        for label in labels
    ]
    return KnownOrganization(id=organization_id, name=name, posts=posts)


_COUNCIL = _organization("council", "City Council", ["Council Member District 1"])
_MAYOR = _organization("mayor", "Office of the Mayor", ["Mayor"])
_MEMBERSHIPS = [
    ExpectedMembership(organization_id="council", role_id="council-member", role_label="Council Member", division="district 1"),
    ExpectedMembership(organization_id="mayor", role_id="mayor", role_label="Mayor"),
]


def _hash(
    url: str = _URL,
    config: PipelineRunConfig = _CONFIG,
    roles: list[str] = _ROLES,
    organizations: list[KnownOrganization] = [_COUNCIL, _MAYOR],
    memberships: list[ExpectedMembership] = _MEMBERSHIPS,
) -> str:
    return prompt_hash(url, config, _OCDID, roles, organizations, memberships)


def test_the_same_inputs_give_the_same_hash():
    assert _hash() == _hash()


def test_a_government_form_change_moves_it():
    """The input the 09-18 hand-listed design would have missed."""
    changed = _CONFIG.model_copy(update={"government_form": GovernmentForm.COUNCIL_MANAGER})

    assert _hash(config=changed) != _hash()


def test_a_renamed_organization_moves_it():
    renamed = _organization("council", "Seattle City Council", ["Council Member District 1"])

    assert _hash(organizations=[renamed, _MAYOR]) != _hash()


def test_a_new_expected_division_moves_it():
    district_2 = ExpectedMembership(organization_id="council", role_id="council-member", role_label="Council Member", division="district 2")

    assert _hash(memberships=[*_MEMBERSHIPS, district_2]) != _hash()


def test_a_new_known_role_moves_it():
    assert _hash(roles=[*_ROLES, "City Attorney"]) != _hash()


def test_a_new_model_moves_it(monkeypatch):
    """A reading by another model is not this one's to reuse."""
    before = _hash()
    monkeypatch.setitem(page_prompts.MODELS_BY_TYPE, "STANDARD", {"model": "another/model", "providers": []})

    assert _hash() != before


def test_each_page_has_its_own():
    """The relevance prompt names the page, so reuse only ever compares a url with itself."""
    assert _hash(url="https://seattle.gov/mayor") != _hash()


def _clock(monkeypatch, day: datetime) -> None:
    """Make the prompt builders think it is `day`."""

    class _Today:
        @staticmethod
        def now():
            return day

    monkeypatch.setattr(open_router_prompts, "datetime", _Today)


def test_the_same_inputs_hash_the_same_on_two_days(monkeypatch):
    """The sent prompt asks who is *currently* serving, so it carries the date; the key must not.

    Keyed on the date, the hash moved every day and no page was ever replayed (0 of 11,925
    prod pages, measured 2026-11-20).
    """
    _clock(monkeypatch, datetime(2026, 8, 1))
    august = _hash()
    _clock(monkeypatch, datetime(2026, 9, 1))

    assert _hash() == august


def test_the_prompt_it_sends_still_carries_the_day(monkeypatch):
    """Only the hash pins the date. The model still has to know what day it is."""
    _clock(monkeypatch, datetime(2026, 8, 1))
    august = page_extraction_prompt([_COUNCIL, _MAYOR], _MEMBERSHIPS, _OCDID, "Seattle city")
    _clock(monkeypatch, datetime(2026, 9, 1))
    september = page_extraction_prompt([_COUNCIL, _MAYOR], _MEMBERSHIPS, _OCDID, "Seattle city")

    assert "2026-08-01" in august
    assert august != september
