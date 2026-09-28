import pytest

from core.organization_derivation import ExistingOrganization, organization_changes_for_form
from shared.schemas import GovernmentForm

GOVERNMENT = ExistingOrganization(id="gov", name="Government", meta_is_default=True)


@pytest.mark.unit
def test_the_default_is_renamed_and_the_rest_created():
    changes = organization_changes_for_form(GovernmentForm.OPEN_TOWN_MEETING, [GOVERNMENT])

    assert changes.rename_default_to == "Select Board"
    assert [o.name for o in changes.organizations_to_create] == ["Town Meeting"]


@pytest.mark.unit
def test_a_one_organization_form_only_renames():
    changes = organization_changes_for_form(GovernmentForm.COUNCIL_MANAGER, [GOVERNMENT])

    assert changes.rename_default_to == "Council"
    assert changes.organizations_to_create == []


@pytest.mark.unit
def test_applying_the_same_form_again_changes_nothing():
    select_board = ExistingOrganization(id="gov", name="Select Board", meta_is_default=True)
    town_meeting = ExistingOrganization(id="tm", name="Town Meeting", meta_is_default=False)

    changes = organization_changes_for_form(
        GovernmentForm.OPEN_TOWN_MEETING, [select_board, town_meeting]
    )

    assert changes.has_no_changes


@pytest.mark.unit
def test_a_hand_made_organization_with_the_name_is_not_renamed_over():
    council = ExistingOrganization(id="council", name="Council", meta_is_default=False)

    changes = organization_changes_for_form(GovernmentForm.MAYOR_COUNCIL, [GOVERNMENT, council])

    assert changes.rename_default_to is None
    assert [o.name for o in changes.organizations_to_create] == ["Office of the Mayor"]
