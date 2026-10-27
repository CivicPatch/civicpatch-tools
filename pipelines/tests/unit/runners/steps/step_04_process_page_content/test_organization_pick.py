"""The organization the model picks: from ours, the default never offered, "none" left to ingest."""

import pytest
from pydantic import ValidationError

from runners.pipeline03_people_collector.schemas import PeopleArrayLLMResponseSchema
from runners.pipeline03_people_collector.steps.step_04_process_page_content.organization_pick import (
    pick_choices,
    pick_response_schema,
    picked_organization_id,
)
from shared.schemas import KnownOrganization

pytestmark = pytest.mark.unit

_SELECTBOARD = KnownOrganization(id="sb", name="Selectboard")
_LISTERS = KnownOrganization(id="bl", name="Board of Listers")
_TOWN_OFFICERS = KnownOrganization(id="to", name="Town Officers", meta_is_default=True)


def test_the_default_is_never_a_choice():
    assert pick_choices([_TOWN_OFFICERS, _SELECTBOARD, _LISTERS]) == ["Selectboard", "Board of Listers"]


def test_the_schema_accepts_a_choice_or_none():
    schema = pick_response_schema(["Selectboard"])

    for organization in ("Selectboard", "none"):
        schema.model_validate({"people": [{"name": "Ann Lee", "label": "Member", "organization": organization}]})


def test_the_schema_refuses_an_organization_we_do_not_have():
    schema = pick_response_schema(["Selectboard"])

    with pytest.raises(ValidationError):
        schema.model_validate({"people": [{"name": "Ann Lee", "label": "Member", "organization": "Planning Commission"}]})


def test_with_nothing_to_pick_the_schema_is_the_plain_one():
    assert pick_response_schema([]) is PeopleArrayLLMResponseSchema


def test_a_pick_becomes_its_organization_s_id_and_none_becomes_no_id():
    organizations = [_SELECTBOARD, _LISTERS]

    assert picked_organization_id("Board of Listers", organizations) == "bl"
    assert picked_organization_id("none", organizations) is None
    assert picked_organization_id(None, organizations) is None
