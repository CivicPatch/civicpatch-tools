"""Pure — each organization's search terms. No mocks."""

import pytest

from runners.people_collector.utils.organization_terms import (
    as_tokens,
    organization_phrases,
    search_phrases,
)
from runners.people_collector.schemas import ExpectedMembership
from shared.schemas import KnownOrganization, Post

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz/government"


def _post(organization_id: str, label: str) -> Post:
    return Post(
        id=f"post-{label}",
        jurisdiction_ocdid=_OCDID,
        organization_id=organization_id,
        role_id="role",
        division_ocdid="ocd-division/country:us/state:zz/place:zz",
        label=label,
    )


def test_each_organization_keeps_its_own_terms():
    """What the frontier ranks by: a council link must know it serves the council, not the mayor."""
    organizations = [
        KnownOrganization(
            id="council", name="City Council", posts=[_post("council", "Council Member, District 3")]
        ),
        KnownOrganization(id="mayor", name="Office of the Mayor", posts=[_post("mayor", "Mayor")]),
    ]

    terms = {
        organization.id: as_tokens(organization_phrases([organization]))
        for organization in organizations
    }

    assert terms == {
        "council": ["council", "member", "district"],
        "mayor": ["mayor"],
    }


def test_text_gets_phrases_and_urls_get_their_tokens():
    """Accordion buttons and page sections match a phrase by substring; a URL path matches tokens.
    "member" alone would open "Become a Member" and keep newsletter blurbs."""
    organizations = [
        KnownOrganization(
            id="council", name="City Council", posts=[_post("council", "Council Member, District 3")]
        ),
    ]

    memberships = [ExpectedMembership(organization_id="council", role_label="Mayor")]

    phrases = search_phrases(organizations, memberships)

    assert phrases == ["City Council", "Council Member, District 3", "Mayor"]
    assert as_tokens(phrases) == ["council", "member", "district", "mayor"]


def test_expected_roles_and_designations_are_searched_once_each():
    """"Position 8" names no division, so it is wording to search for and nothing more."""
    organizations = [KnownOrganization(id="council", name="City Council", posts=[])]
    memberships = [
        ExpectedMembership(organization_id="council", role_label="Council Member", designations=["Position 8"]),
        ExpectedMembership(
            organization_id="council", role_label="Council Member", division="ward 2", designations=["Position 8"]
        ),
    ]

    assert search_phrases(organizations, memberships) == [
        "City Council",
        "Council Member",
        "Position 8",
    ]
