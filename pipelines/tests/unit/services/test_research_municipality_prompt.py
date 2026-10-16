"""The research prompt: the form's organizations reach it as a hint, and it asks which body each
official sits on. These pin what reaches the prompt at all."""

import pytest

from services.google_gemini.prompts import research_municipality_prompt
from shared.schemas import KnownOrganization

pytestmark = pytest.mark.unit

_SEATTLE = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"


def test_each_organizations_usual_roles_are_offered_as_a_hint():
    organizations = [
        KnownOrganization(id="council", name="Council", role_labels=["Council Member"]),
        KnownOrganization(id="mayor", name="Office of the Mayor", role_labels=["Mayor"]),
    ]

    prompt = research_municipality_prompt(_SEATTLE, "Seattle city", organizations)

    assert "- Council: usually Council Member" in prompt
    assert "- Office of the Mayor: usually Mayor" in prompt
    assert "even ones not named here" in prompt


def test_no_hint_while_no_organization_has_usual_roles():
    default = KnownOrganization(id="government", name="Government", meta_is_default=True)

    prompt = research_municipality_prompt(_SEATTLE, "Seattle city", [default])

    assert "usually" not in prompt


def test_it_asks_which_body_each_official_sits_on():
    prompt = research_municipality_prompt(_SEATTLE, "Seattle city", [])

    assert '"organization": "Body they sit on"' in prompt
