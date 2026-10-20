"""Pure — each organization's search terms. No mocks."""

import pytest

from runners.pipeline03_people_collector.utils.organization_terms import (
    as_tokens,
    organization_phrases,
    expected_divisions,
    government_form_role_labels,
    roles_to_look_for,
    search_phrases,
)
from runners.pipeline03_people_collector.schemas import ExpectedMembership
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
        role_label=label,
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


def test_roles_to_look_for_names_an_organization_nobody_is_expected_in():
    select_board = KnownOrganization(id="select", name="Select Board", role_labels=["Select Board Member"])
    town_meeting = KnownOrganization(id="meeting", name="Town Meeting", role_labels=["Moderator"])
    expected = [ExpectedMembership(organization_id="select", role_label="Select Board Member")]

    assert roles_to_look_for(expected, [select_board, town_meeting]) == ["Select Board Member", "Moderator"]


def test_the_forms_role_labels_come_only_from_organizations_nobody_is_expected_in():
    expected_in = KnownOrganization(id="a", name="Select Board", role_labels=["Select Board Member"])
    nobody = KnownOrganization(id="b", name="Town Meeting", role_labels=["Moderator", "Town Meeting Member"])
    memberships = [ExpectedMembership(organization_id="a", role_label="Select Board Member")]

    assert government_form_role_labels([expected_in, nobody], memberships) == ["Moderator", "Town Meeting Member"]


def test_expected_divisions_skip_at_large_and_repeat_once():
    memberships = [
        ExpectedMembership(organization_id="a", role_label="Council Member", division="ward 1"),
        ExpectedMembership(organization_id="a", role_label="Council Member", division="ward 1"),
        ExpectedMembership(organization_id="a", role_label="Mayor"),
    ]

    assert expected_divisions(memberships) == ["ward 1"]
