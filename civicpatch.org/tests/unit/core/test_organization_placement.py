"""Placement of a scraped record: the model's pick, else the organization whose form lists its post
role, else the one of those the person already sits in, else the default. Roles and organizations
as open-data's Vermont config has them."""

import pytest

from core.organization_placement import PlaceableOrganization, placed_organization_id, role_ids_of
from shared.schemas import Role, RoleConfig, SelectionMethod
from shared.utils.taxonomy import build_taxonomy

_TOWN = "ocd-jurisdiction/country:us/state:vt/place:brattleboro/government"
_COUNTY = "ocd-jurisdiction/country:us/state:wa/county:kitsap/government"

TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="member", label="Member", aliases=["Select Board Member", "Selectboard Member", "Trustee"]),
            Role(id="chair", label="Chair", is_unique=True, selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
            Role(id="vice-chair", label="Vice Chair", is_unique=True, selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
            Role(id="clerk", label="Clerk", is_unique=True, aliases=["Town Clerk"]),
            Role(id="moderator", label="Moderator", is_unique=True),
            Role(id="lister", label="Lister", aliases=["Board of Listers"]),
            Role(id="cemetery-commissioner", label="Cemetery Commissioner", aliases=["Board of Cemetery Commissioners"]),
            Role(id="library-trustee", label="Library Trustee", aliases=["Board of Library Trustees"]),
            Role(id="commissioner", label="Commissioner"),
        ]
    )
)


def _organization(organization_id: str, *role_labels: str) -> PlaceableOrganization:
    return PlaceableOrganization(id=organization_id, role_ids=role_ids_of(list(role_labels), TAXONOMY))


BRATTLEBORO = [
    _organization("selectboard", "Select Board Member", "Chair", "Vice Chair"),
    _organization("town-meeting", "Moderator"),
    _organization("town-officers", "Town Clerk"),
    _organization("listers", "Lister"),
    _organization("cemetery", "Cemetery Commissioner"),
    _organization("library", "Library Trustee"),
]
KITSAP = [_organization("board", "Commissioner", "Chair"), _organization("county-officers")]
NOBODY: set[str] = set()


def _place(label: str, pick: str | None, held: set[str] = NOBODY) -> str:
    return placed_organization_id(label, pick, BRATTLEBORO, "town-officers", held, _TOWN, TAXONOMY)


@pytest.mark.unit
def test_the_pick_wins_over_the_role():
    """Katherine Dowd, "Lister and Clerk" on the listers page: she clerks that board, and the model
    saw it; the form's rule (clerk -> Town Officers) would have been wrong."""
    assert _place("Lister and Clerk", "listers") == "listers"


@pytest.mark.unit
def test_a_clerk_with_no_pick_goes_where_the_form_lists_the_clerk():
    assert _place("Town Clerk", None) == "town-officers"


@pytest.mark.unit
def test_a_member_with_no_pick_goes_where_they_already_sit():
    assert _place("Member", None, held={"selectboard"}) == "selectboard"


@pytest.mark.unit
def test_a_member_with_no_pick_and_no_post_goes_to_the_default():
    assert _place("Member", None) == "town-officers"


@pytest.mark.unit
def test_a_chair_with_no_pick_goes_to_the_board_the_person_sits_on():
    """A chair is a member post, so the form alone never places it (step 2); the person's seat does."""
    assert _place("Chair", None, held={"selectboard"}) == "selectboard"
    assert _place("Chair", None) == "town-officers"


@pytest.mark.unit
def test_a_chair_of_a_board_whose_form_lists_no_chair_goes_to_the_default():
    """The config lists each label once per form, so the listers' chair is not a candidate here;
    on the page the model's pick covers it."""
    assert _place("Chair", None, held={"listers"}) == "town-officers"


@pytest.mark.unit
def test_a_role_no_organization_lists_goes_to_the_default_without_a_pick():
    assert placed_organization_id("Sheriff", None, KITSAP, "county-officers", NOBODY, _COUNTY, TAXONOMY) == "county-officers"


@pytest.mark.unit
def test_a_commissioner_who_chairs_goes_to_the_commissioners():
    assert _place("Cemetery Commissioner, Chair", None) == "cemetery"


@pytest.mark.unit
def test_a_library_trustee_who_chairs_goes_to_the_library_trustees():
    assert _place("Library Trustee Chair", None) == "library"


@pytest.mark.unit
def test_a_role_two_organizations_list_goes_to_the_default_when_the_person_sits_on_neither():
    both = [*BRATTLEBORO, _organization("other-clerks", "Town Clerk")]

    assert placed_organization_id("Town Clerk", None, both, "town-officers", NOBODY, _TOWN, TAXONOMY) == "town-officers"
