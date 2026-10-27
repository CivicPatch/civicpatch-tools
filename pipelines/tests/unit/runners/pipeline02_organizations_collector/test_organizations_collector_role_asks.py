"""Which roles EXTRACT asks about, from a jurisdiction's merged config and its government form."""

import pytest

from runners.pipeline02_organizations_collector.role_asks import presiding_asks, role_asks
from shared.schemas import GovernmentForm, SelectionMethod
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import ConfigFile, ConfigRole, GovernmentFormConfig, merged_config

pytestmark = pytest.mark.unit

_ROLES = ConfigFile(
    roles=[
        ConfigRole(id="mayor", label="Mayor", is_unique=True),
        ConfigRole(id="member", label="Member", aliases=["Council Member", "Select Board Member", "selectboard member"]),
        ConfigRole(id="chair", label="Chair", is_unique=True, selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
        ConfigRole(id="moderator", label="Moderator", is_unique=True),
    ]
)
_FORMS = ConfigFile(
    government_forms={
        GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(
            organizations=[
                DerivedOrganization(name="Council", role_labels=["Council Member"]),
                DerivedOrganization(name="Office of the Mayor", role_labels=["Mayor"]),
            ]
        ),
        GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
            suffixes=["town"],
            organizations=[
                DerivedOrganization(name="Select Board", role_labels=["Select Board Member", "Chair"]),
                DerivedOrganization(name="Town Meeting", role_labels=["Moderator"]),
            ],
        ),
    }
)
CONFIG = merged_config(_ROLES, _FORMS, None)


def _asked(asks) -> list[tuple[str, str, str]]:
    return [(ask.organization_name, ask.role_id, ask.role_label) for ask in asks]


def test_a_set_form_asks_about_its_organizations_roles():
    assert _asked(role_asks(CONFIG, "Stowe town", GovernmentForm.OPEN_TOWN_MEETING)) == [
        ("Select Board", "member", "Select Board Member"),
        ("Select Board", "chair", "Chair"),
        ("Town Meeting", "moderator", "Moderator"),
    ]


def test_a_role_chosen_by_members_is_a_presiding_candidate_of_the_first_organization_though_no_form_lists_it():
    assert _asked(presiding_asks(CONFIG, "Burlington city", GovernmentForm.MAYOR_COUNCIL)) == [("Council", "chair", "Chair")]
    assert "chair" not in [ask.role_id for ask in role_asks(CONFIG, "Burlington city", GovernmentForm.MAYOR_COUNCIL)]


def test_a_candidate_the_form_already_lists_is_asked_on_its_own_not_again_with_the_candidates():
    assert presiding_asks(CONFIG, "Stowe town", GovernmentForm.OPEN_TOWN_MEETING) == []


def test_with_no_form_set_the_forms_its_name_allows_are_asked_about():
    assert _asked(role_asks(CONFIG, "Stowe town", None)) == _asked(role_asks(CONFIG, "Stowe town", GovernmentForm.OPEN_TOWN_MEETING))


def test_a_role_two_forms_name_is_asked_once_under_the_first():
    asks = role_asks(CONFIG, "Burlington city", None)

    assert [ask.role_id for ask in asks].count("member") == 1


def test_the_question_names_every_way_the_law_may_write_the_role():
    member = role_asks(CONFIG, "Stowe town", GovernmentForm.OPEN_TOWN_MEETING)[0]

    assert member.names == ["Select Board Member", "Member", "Council Member", "selectboard member"]


# Vermont's town forms list the § 2646 officers after the Selectboard and Town Meeting, so the
# presiding candidates still hang on the Selectboard while the clerk is asked under Town Officers.
_VT_ROLES = ConfigFile(
    roles=[
        ConfigRole(id="member", label="Member", aliases=["Select Board Member"]),
        ConfigRole(id="chair", label="Chair", is_unique=True, selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
        ConfigRole(id="moderator", label="Moderator", is_unique=True),
        ConfigRole(id="clerk", label="Clerk", is_unique=True, aliases=["Town Clerk"]),
        ConfigRole(id="treasurer", label="Treasurer", is_unique=True, aliases=["Town Treasurer"]),
        ConfigRole(id="lister", label="Lister"),
    ]
)
_VT_FORMS = ConfigFile(
    government_forms={
        GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
            suffixes=["town"],
            organizations=[
                DerivedOrganization(name="Selectboard", role_labels=["Select Board Member"]),
                DerivedOrganization(name="Town Meeting", role_labels=["Moderator"]),
                DerivedOrganization(name="Town Officers", role_labels=["Town Clerk", "Town Treasurer"]),
                DerivedOrganization(name="Board of Listers", role_labels=["Lister"]),
            ],
        ),
    }
)
_VT_CONFIG = merged_config(_VT_ROLES, _VT_FORMS, None)


def test_town_officers_are_asked_under_their_own_organization_after_the_boards():
    assert _asked(role_asks(_VT_CONFIG, "Johnson town", GovernmentForm.OPEN_TOWN_MEETING)) == [
        ("Selectboard", "member", "Select Board Member"),
        ("Town Meeting", "moderator", "Moderator"),
        ("Town Officers", "clerk", "Town Clerk"),
        ("Town Officers", "treasurer", "Town Treasurer"),
        ("Board of Listers", "lister", "Lister"),
    ]
    assert _asked(presiding_asks(_VT_CONFIG, "Johnson town", GovernmentForm.OPEN_TOWN_MEETING)) == [("Selectboard", "chair", "Chair")]
