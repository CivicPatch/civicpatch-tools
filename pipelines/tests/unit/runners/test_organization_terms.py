"""Pure — each organization's search terms. No mocks."""

import pytest

from runners.people_collector.utils.organization_terms import (
    as_tokens,
    organization_phrases,
    search_phrases,
)
from shared.schemas import KnownOrganization, Membership, Post

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
        organization.id: as_tokens(organization_phrases([organization], []))
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

    phrases = search_phrases(organizations, [], ["Mayor", "City Council"])

    assert phrases == ["City Council", "Council Member, District 3", "Mayor"]
    assert as_tokens(phrases) == ["council", "member", "district", "mayor"]


def _membership(organization_id: str, label: str | None, source_labels: list[str]) -> Membership:
    return Membership(
        post_id="post",
        organization_id=organization_id,
        label=label,
        source_labels=source_labels,
        role_id="role",
        division_ocdid="ocd-division/country:us/state:zz/place:zz",
        role_label="Council Member",
    )


def test_membership_labels_are_how_the_site_words_the_post():
    """A member's labels belong to their organization: the one a human set, and the page's own
    wording — "Councilmember Pos. 8" is what a section heading or accordion actually says."""
    organizations = [
        KnownOrganization(id="council", name="City Council", posts=[]),
        KnownOrganization(id="schools", name="School Board", posts=[]),
    ]
    memberships = [
        _membership("council", "Mayor Pro Tem", ["Councilmember Pos. 8"]),
        _membership("schools", None, ["Trustee"]),
    ]

    terms = {
        organization.id: as_tokens(organization_phrases([organization], memberships))
        for organization in organizations
    }

    assert search_phrases(organizations, memberships, []) == [
        "City Council",
        "Mayor Pro Tem",
        "Councilmember Pos. 8",
        "School Board",
        "Trustee",
    ]
    assert terms == {
        "council": ["council", "mayor", "councilmember"],
        "schools": ["school", "board", "trustee"],
    }
