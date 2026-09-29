import pytest

from core.organization_derivation import ExistingOrganization, organization_changes, with_role_labels
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization, organizations_for

GOVERNMENT = ExistingOrganization(id="gov", name="Government", meta_is_default=True)
ORIGINAL_DEFAULT_NAME = "Government"


@pytest.mark.unit
def test_the_default_is_renamed_and_the_rest_created():
    changes = organization_changes(
        organizations_for(GovernmentForm.OPEN_TOWN_MEETING), [GOVERNMENT], ORIGINAL_DEFAULT_NAME
    )

    assert changes.rename_default_to == "Select Board"
    assert [o.name for o in changes.organizations_to_create] == ["Town Meeting"]


@pytest.mark.unit
def test_a_one_organization_form_only_renames():
    changes = organization_changes(
        organizations_for(GovernmentForm.COUNCIL_MANAGER), [GOVERNMENT], ORIGINAL_DEFAULT_NAME
    )

    assert changes.rename_default_to == "Council"
    assert changes.organizations_to_create == []


@pytest.mark.unit
def test_applying_the_same_organizations_again_changes_nothing():
    select_board = ExistingOrganization(id="gov", name="Select Board", meta_is_default=True)
    town_meeting = ExistingOrganization(id="tm", name="Town Meeting", meta_is_default=False)

    changes = organization_changes(
        organizations_for(GovernmentForm.OPEN_TOWN_MEETING),
        [select_board, town_meeting],
        ORIGINAL_DEFAULT_NAME,
    )

    assert changes.has_no_changes


@pytest.mark.unit
def test_a_hand_made_organization_with_the_name_is_not_renamed_over():
    council = ExistingOrganization(id="council", name="Council", meta_is_default=False)

    changes = organization_changes(
        organizations_for(GovernmentForm.MAYOR_COUNCIL), [GOVERNMENT, council], ORIGINAL_DEFAULT_NAME
    )

    assert changes.rename_default_to is None
    assert [o.name for o in changes.organizations_to_create] == ["Office of the Mayor"]


@pytest.mark.unit
def test_a_default_renamed_by_hand_keeps_its_name():
    aldermen = ExistingOrganization(id="gov", name="Board of Aldermen", meta_is_default=True)

    changes = organization_changes(
        organizations_for(GovernmentForm.MAYOR_COUNCIL), [aldermen], ORIGINAL_DEFAULT_NAME
    )

    assert changes.rename_default_to is None
    assert [o.name for o in changes.organizations_to_create] == ["Office of the Mayor"]


@pytest.mark.unit
def test_nothing_derived_changes_nothing():
    assert organization_changes([], [GOVERNMENT], ORIGINAL_DEFAULT_NAME).has_no_changes


@pytest.mark.unit
def test_a_county_board_renames_the_default():
    board = DerivedOrganization(name="Commissioners Court", role_labels=["Commissioner"])

    changes = organization_changes([board], [GOVERNMENT], ORIGINAL_DEFAULT_NAME)

    assert changes.rename_default_to == "Commissioners Court"


@pytest.mark.unit
def test_each_organization_gets_the_role_labels_derived_under_its_name():
    derived = organizations_for(GovernmentForm.OPEN_TOWN_MEETING)
    organizations = [
        {"id": "a", "name": "Select Board", "posts": []},
        {"id": "b", "name": "Town Meeting", "posts": []},
        {"id": "c", "name": "School Committee", "posts": []},
    ]

    labelled = with_role_labels(organizations, derived)

    assert [o["role_labels"] for o in labelled] == [
        ["Select Board Chair", "Select Board Vice Chair", "Select Board Member"],
        ["Moderator"],
        [],
    ]
    assert "role_labels" not in organizations[0]
