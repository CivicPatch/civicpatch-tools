"""Which organizations a jurisdiction gets: its law's once answered, else its merged config's."""

from datetime import datetime, timezone

import pytest

from core.organization_build import (
    GovernmentFormInputs,
    form_organization_rows,
    law_organization_names,
    organizations_not_in_law,
)
from shared.schemas import (
    GoverningLawOrganizations,
    GoverningLawOrganizationsExtras,
    GoverningLawPost,
    GovernmentForm,
    QuoteScope,
    Source,
    SourceExtras,
)
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import ConfigFile, ConfigRole, GovernmentFormConfig, merged_config

pytestmark = pytest.mark.unit

_SOURCE = Source(
    url="https://example.gov/charter",
    note="five members",
    extras=SourceExtras(source_page_id="charter", matched_in=QuoteScope.SENTENCE),
)


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
    return merged_config(country.model_copy(update={"roles": roles.roles}), state)


def _rows(name: str, government_form: GovernmentForm | None = None, law_names: list[str] | None = None):
    inputs = GovernmentFormInputs(
        jurisdiction_ocdid="ocd-jurisdiction/x", name=name, government_form=government_form, law_organization_names=law_names
    )
    return [row.name for row in form_organization_rows(_config(), [inputs])]


def test_a_town_with_no_saved_form_gets_what_its_two_forms_share():
    assert _rows("Essex town") == ["Selectboard", "Town Officers", "Board of Listers", "Town Meeting"]


def test_a_city_with_no_saved_form_gets_only_what_every_candidate_form_has():
    assert _rows("Barre city") == ["Council"]


def test_a_saved_form_gives_all_of_its_organizations():
    assert _rows("Burlington city", GovernmentForm.MAYOR_COUNCIL) == ["Council", "Office of the Mayor"]


def test_a_village_has_one_form_so_it_needs_no_saved_one():
    assert _rows("Hyde Park village") == ["Board of Trustees", "Village Officers"]


def test_a_name_with_no_legal_status_word_falls_back_to_the_country_forms_and_what_they_share():
    assert _rows("Somewhere") == ["Council"]


def test_a_place_whose_law_was_read_gets_the_organizations_its_law_names_whatever_its_form():
    assert _rows("Burlington city", GovernmentForm.MAYOR_COUNCIL, law_names=["Council", "Board of Finance"]) == [
        "Council",
        "Board of Finance",
    ]


def _post(organization: str, role: str = "member") -> GoverningLawPost:
    return GoverningLawPost(role=role, label=role, organization_id=organization, sources=[_SOURCE])


def _answer(*posts: GoverningLawPost) -> GoverningLawOrganizations:
    return GoverningLawOrganizations(
        posts=list(posts),
        extras=GoverningLawOrganizationsExtras(governing_law_collected_at=datetime(2026, 11, 24, tzinfo=timezone.utc)),
    )


def test_the_laws_organizations_are_the_ones_its_posts_name_once_each_in_order():
    answer = _answer(_post("Council"), _post("Council", "mayor"), _post("Board of Finance"))

    assert law_organization_names(answer) == ["Council", "Board of Finance"]


def test_no_answer_or_one_naming_no_posts_leaves_the_config_to_decide():
    assert law_organization_names(None) is None
    assert law_organization_names(_answer()) is None


def test_the_organizations_the_law_does_not_name_are_picked_out_by_name():
    organizations = {"1": "Council", "2": "Town Officers", "3": "Board of Finance"}

    assert organizations_not_in_law(organizations, ["Council", "Board of Finance"]) == ["2"]

