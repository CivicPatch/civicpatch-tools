"""Which organizations a merged config gives each jurisdiction when its file merges."""

import pytest

from core.organization_build import GovernmentFormInputs, form_organization_rows
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import ConfigFile, ConfigRole, GovernmentFormConfig, merged_config

pytestmark = pytest.mark.unit


def _organization(name: str, *labels: str) -> DerivedOrganization:
    return DerivedOrganization(name=name, role_labels=list(labels))


def _config():
    roles = ConfigFile(
        roles=[
            ConfigRole(id="member", label="Member", aliases=["Select Board Member", "Council Member", "Trustee"]),
            ConfigRole(id="mayor", label="Mayor"),
            ConfigRole(id="clerk", label="Clerk", aliases=["Town Clerk", "Village Clerk"]),
            ConfigRole(id="moderator", label="Moderator"),
            ConfigRole(id="town-meeting-member", label="Town Meeting Member"),
            ConfigRole(id="lister", label="Lister"),
            ConfigRole(id="president", label="President", aliases=["Village President"]),
        ]
    )
    country = ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(
                organizations=[_organization("Council", "Council Member"), _organization("Office of the Mayor", "Mayor")]
            ),
            GovernmentForm.COUNCIL_MANAGER: GovernmentFormConfig(
                organizations=[_organization("Council", "Council Member", "Mayor")]
            ),
        }
    )
    town = [
        _organization("Selectboard", "Select Board Member"),
        _organization("Town Officers", "Town Clerk"),
        _organization("Board of Listers", "Lister"),
    ]
    state = ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(suffixes=["city"]),
            GovernmentForm.COUNCIL_MANAGER: GovernmentFormConfig(suffixes=["city"]),
            GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
                suffixes=["town"], organizations=[*town, _organization("Town Meeting", "Moderator")]
            ),
            GovernmentForm.REPRESENTATIVE_TOWN_MEETING: GovernmentFormConfig(
                suffixes=["town"], organizations=[*town, _organization("Town Meeting", "Moderator", "Town Meeting Member")]
            ),
            GovernmentForm.VILLAGE_BOARD: GovernmentFormConfig(
                suffixes=["village"],
                organizations=[_organization("Board of Trustees", "Trustee", "Village President"), _organization("Village Officers", "Village Clerk")],
            ),
        }
    )
    return merged_config(roles, country, state)


def _rows(name: str, government_form: GovernmentForm | None = None):
    inputs = GovernmentFormInputs(jurisdiction_ocdid="ocd-jurisdiction/x", name=name, government_form=government_form)
    return [(row.name, row.role_labels) for row in form_organization_rows(_config(), [inputs])]


def test_a_town_with_no_saved_form_gets_what_its_two_forms_share_with_labels_an_alias_gives():
    assert _rows("Essex town") == [
        ("Selectboard", {"member": "Select Board Member"}),
        ("Town Officers", {"clerk": "Town Clerk"}),
        ("Board of Listers", {}),
        ("Town Meeting", {}),
    ]


def test_a_city_with_no_saved_form_gets_only_what_every_candidate_form_has():
    assert _rows("Barre city") == [("Council", {"member": "Council Member"})]


def test_a_saved_form_gives_all_of_its_organizations():
    assert _rows("Burlington city", GovernmentForm.MAYOR_COUNCIL) == [
        ("Council", {"member": "Council Member"}),
        ("Office of the Mayor", {}),
    ]


def test_a_village_has_one_form_so_it_needs_no_saved_one():
    assert _rows("Hyde Park village") == [
        ("Board of Trustees", {"member": "Trustee", "president": "Village President"}),
        ("Village Officers", {"clerk": "Village Clerk"}),
    ]


def test_a_name_with_no_legal_status_word_falls_back_to_the_country_forms_and_what_they_share():
    assert _rows("Somewhere") == [("Council", {"member": "Council Member"})]
