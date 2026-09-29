import pytest
from pydantic import ValidationError
from shared.schemas import GovernmentForm
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import (
    ConfigFile,
    ConfigRole,
    FormConfig,
    allowed_forms,
    form_organizations,
    merged_config,
)

_COUNCIL = DerivedOrganization(name="Council", role_labels=["Council Member"])
_SELECT_BOARD = DerivedOrganization(name="Select Board", role_labels=["Select Board Member"])

_COUNTRY = ConfigFile(
    roles=[
        ConfigRole(id="mayor", label="Mayor", is_unique=True),
        ConfigRole(id="council-member", label="Council Member", aliases=["councilmember"]),
        ConfigRole(id="select-board-member", label="Select Board Member"),
    ],
    government_forms={
        GovernmentForm.MAYOR_COUNCIL: FormConfig(organizations=[_COUNCIL]),
        GovernmentForm.COUNCIL_MANAGER: FormConfig(organizations=[_COUNCIL]),
        GovernmentForm.OPEN_TOWN_MEETING: FormConfig(organizations=[_SELECT_BOARD]),
    },
)


def test_state_roles_follow_the_country_roles_in_priority():
    state = ConfigFile(roles=[ConfigRole(id="assessor", label="Assessor")])

    roles = merged_config(_COUNTRY, state).roles.roles

    assert [(role.id, role.priority) for role in roles] == [
        ("mayor", 0),
        ("council-member", 1),
        ("select-board-member", 2),
        ("assessor", 3),
    ]


def test_no_state_file_is_the_country_alone():
    assert [role.id for role in merged_config(_COUNTRY, None).roles.roles] == [
        "mayor",
        "council-member",
        "select-board-member",
    ]


def test_a_state_cannot_redefine_a_country_role():
    state = ConfigFile(roles=[ConfigRole(id="mayor", label="Town Mayor")])

    with pytest.raises(ValueError, match="'mayor' is listed twice"):
        merged_config(_COUNTRY, state)


def test_a_state_alias_cannot_name_a_country_role():
    state = ConfigFile(roles=[ConfigRole(id="alderperson", label="Alderperson", aliases=["Council-Member"])])

    with pytest.raises(ValueError, match="names both 'council-member' and 'alderperson'"):
        merged_config(_COUNTRY, state)


def test_one_file_cannot_give_two_roles_one_alias():
    with pytest.raises(ValidationError, match="names both"):
        ConfigFile(
            roles=[
                ConfigRole(id="chair", label="Chair", aliases=["presiding officer"]),
                ConfigRole(id="president", label="President", aliases=["presiding officer"]),
            ]
        )


def test_a_state_form_must_be_a_country_form():
    state = ConfigFile(government_forms={GovernmentForm.COMMISSION: FormConfig()})

    with pytest.raises(ValueError, match="commission is not a form at this level"):
        merged_config(_COUNTRY, state)


def test_a_country_form_needs_organizations():
    country = ConfigFile(government_forms={GovernmentForm.MAYOR_COUNCIL: FormConfig()})

    with pytest.raises(ValueError, match="mayor_council has no organizations"):
        merged_config(country, None)


def test_an_organization_role_must_be_a_role():
    state = ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: FormConfig(
                organizations=[DerivedOrganization(name="Board of Aldermen", role_labels=["Alderman"])]
            )
        }
    )

    with pytest.raises(ValueError, match="Board of Aldermen's role 'Alderman' is not a role"):
        merged_config(_COUNTRY, state)


def test_an_organization_role_may_be_an_alias():
    state = ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: FormConfig(
                organizations=[DerivedOrganization(name="Council", role_labels=["Councilmember"])]
            )
        }
    )

    assert merged_config(_COUNTRY, state)


def test_without_state_forms_every_country_form_is_allowed():
    config = merged_config(_COUNTRY, None)

    assert allowed_forms(config, "Springfield city") == [
        GovernmentForm.MAYOR_COUNCIL,
        GovernmentForm.COUNCIL_MANAGER,
        GovernmentForm.OPEN_TOWN_MEETING,
    ]


def test_a_suffixed_state_form_decides_only_names_with_that_suffix():
    state = ConfigFile(
        government_forms={GovernmentForm.OPEN_TOWN_MEETING: FormConfig(suffixes=["town"])}
    )
    config = merged_config(_COUNTRY, state)

    assert allowed_forms(config, "Millbury town") == [GovernmentForm.OPEN_TOWN_MEETING]
    assert len(allowed_forms(config, "Worcester city")) == 3


def test_state_forms_without_suffixes_narrow_the_state():
    state = ConfigFile(government_forms={GovernmentForm.COUNCIL_MANAGER: FormConfig()})

    assert allowed_forms(merged_config(_COUNTRY, state), "Springfield city") == [
        GovernmentForm.COUNCIL_MANAGER
    ]


def test_a_state_renames_a_forms_organizations():
    aldermen = DerivedOrganization(name="Board of Aldermen", role_labels=["Council Member"])
    state = ConfigFile(
        government_forms={GovernmentForm.MAYOR_COUNCIL: FormConfig(organizations=[aldermen])}
    )
    config = merged_config(_COUNTRY, state)

    assert form_organizations(config, GovernmentForm.MAYOR_COUNCIL) == [aldermen]


def test_a_state_form_without_organizations_keeps_the_countrys():
    state = ConfigFile(
        government_forms={GovernmentForm.OPEN_TOWN_MEETING: FormConfig(suffixes=["town"])}
    )

    assert form_organizations(merged_config(_COUNTRY, state), GovernmentForm.OPEN_TOWN_MEETING) == [
        _SELECT_BOARD
    ]
