"""Placement of a scraped record: its post role's organization, else the model's pick, else the
default. Roles and organizations as open-data's Vermont config has them."""

import pytest

from core.organization_placement import PlaceableOrganization, placed_organization_id, role_ids_of
from shared.schemas import Role, RoleConfig, SelectionMethod
from shared.utils.taxonomy import build_taxonomy

_TOWN = "ocd-jurisdiction/country:us/state:vt/place:whiting/government"
_COUNTY = "ocd-jurisdiction/country:us/state:wa/county:kitsap/government"

TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="member", label="Member", aliases=["Select Board Member", "Selectboard Member", "Trustee"]),
            Role(id="chair", label="Chair", is_unique=True, selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
            Role(id="vice-chair", label="Vice Chair", is_unique=True, selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
            Role(id="clerk", label="Clerk", is_unique=True, aliases=["Town Clerk"]),
            Role(id="moderator", label="Moderator", is_unique=True),
            Role(id="cemetery-commissioner", label="Cemetery Commissioner", aliases=["Board of Cemetery Commissioners"]),
            Role(id="library-trustee", label="Library Trustee", aliases=["Board of Library Trustees"]),
            Role(id="commissioner", label="Commissioner"),
        ]
    )
)


def _organization(organization_id: str, *role_labels: str) -> PlaceableOrganization:
    return PlaceableOrganization(id=organization_id, role_ids=role_ids_of(list(role_labels), TAXONOMY))


WHITING = [
    _organization("selectboard", "Select Board Member", "Chair", "Vice Chair"),
    _organization("town-meeting", "Moderator"),
    _organization("town-officers", "Town Clerk"),
    _organization("cemetery", "Cemetery Commissioner"),
    _organization("library", "Library Trustee"),
]
KITSAP = [_organization("board", "Commissioner", "Chair"), _organization("county-officers")]


def _place_in_whiting(label: str, pick: str | None) -> str:
    return placed_organization_id(label, pick, WHITING, "town-officers", _TOWN, TAXONOMY)


@pytest.mark.unit
def test_the_clerk_goes_where_the_form_lists_the_clerk_whatever_the_pick():
    assert _place_in_whiting("Town Clerk", "town-meeting") == "town-officers"


@pytest.mark.unit
def test_a_member_goes_to_the_pick():
    assert _place_in_whiting("Member", "selectboard") == "selectboard"


@pytest.mark.unit
def test_a_member_with_no_pick_goes_to_the_default():
    assert _place_in_whiting("Member", None) == "town-officers"


@pytest.mark.unit
def test_a_role_no_organization_lists_goes_to_the_default_without_a_pick():
    assert placed_organization_id("Sheriff", None, KITSAP, "county-officers", _COUNTY, TAXONOMY) == "county-officers"


@pytest.mark.unit
def test_a_chair_rides_on_the_pick():
    assert _place_in_whiting("Selectboard Chair", "selectboard") == "selectboard"


@pytest.mark.unit
def test_a_commissioner_who_chairs_goes_to_the_commissioners():
    assert _place_in_whiting("Cemetery Commissioner, Chair", None) == "cemetery"


@pytest.mark.unit
def test_a_library_trustee_who_chairs_goes_to_the_library_trustees():
    assert _place_in_whiting("Library Trustee Chair", None) == "library"


@pytest.mark.unit
def test_a_role_two_organizations_list_goes_to_the_pick():
    both = [*WHITING, _organization("other-clerks", "Town Clerk")]

    assert placed_organization_id("Town Clerk", "other-clerks", both, "town-officers", _TOWN, TAXONOMY) == "other-clerks"
