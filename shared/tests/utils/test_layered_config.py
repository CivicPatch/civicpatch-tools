import pytest
from pydantic import ValidationError
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import (
    COUNTRY_ROLES_PATH,
    ConfigFile,
    ConfigRole,
    FormConfig,
    allowed_forms,
    check_roles_distinct_across,
    derived_organizations,
    form_organizations,
    jurisdiction_config,
    merged_config,
    resolve_government_form,
)

_COUNCIL = DerivedOrganization(name="Council", role_labels=["Council Member"])
_SELECT_BOARD = DerivedOrganization(name="Select Board", role_labels=["Select Board Member"])

_COUNTRY_ROLES = ConfigFile(
    roles=[
        ConfigRole(id="mayor", label="Mayor", is_unique=True),
        ConfigRole(id="council-member", label="Council Member", aliases=["councilmember"]),
        ConfigRole(id="select-board-member", label="Select Board Member"),
    ],
)

_COUNTRY_FORMS = ConfigFile(
    government_forms={
        GovernmentForm.MAYOR_COUNCIL: FormConfig(organizations=[_COUNCIL]),
        GovernmentForm.COUNCIL_MANAGER: FormConfig(organizations=[_COUNCIL]),
        GovernmentForm.OPEN_TOWN_MEETING: FormConfig(organizations=[_SELECT_BOARD]),
    },
)


def test_state_roles_follow_the_country_roles_in_priority():
    state = ConfigFile(roles=[ConfigRole(id="assessor", label="Assessor")])

    roles = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state).roles.roles

    assert [(role.id, role.priority) for role in roles] == [
        ("mayor", 0),
        ("council-member", 1),
        ("select-board-member", 2),
        ("assessor", 3),
    ]


def test_no_state_file_is_the_country_alone():
    assert [role.id for role in merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, None).roles.roles] == [
        "mayor",
        "council-member",
        "select-board-member",
    ]


def test_a_state_cannot_redefine_a_country_role():
    state = ConfigFile(roles=[ConfigRole(id="mayor", label="Town Mayor")])

    with pytest.raises(ValueError, match="'mayor' is listed twice"):
        merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)


def test_a_state_alias_cannot_name_a_country_role():
    state = ConfigFile(roles=[ConfigRole(id="alderperson", label="Alderperson", aliases=["Council-Member"])])

    with pytest.raises(ValueError, match="names both 'council-member' and 'alderperson'"):
        merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)


def test_country_roles_and_forms_stay_in_their_own_files():
    with pytest.raises(ValueError, match="separate files"):
        merged_config(_COUNTRY_FORMS, _COUNTRY_FORMS, None)
    with pytest.raises(ValueError, match="separate files"):
        merged_config(_COUNTRY_ROLES, _COUNTRY_ROLES, None)


def test_two_states_that_never_merge_still_cannot_share_an_alias():
    """The database keeps one row per alias, whatever state it came from."""
    tennessee = ConfigFile(roles=[ConfigRole(id="county-mayor", label="County Mayor", aliases=["executive"])])
    hawaii = ConfigFile(roles=[ConfigRole(id="county-executive", label="County Executive", aliases=["executive"])])

    with pytest.raises(ValueError, match="names both 'county-mayor' and 'county-executive'"):
        check_roles_distinct_across([_COUNTRY_ROLES, tennessee, hawaii])


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
        merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)


def test_a_country_form_needs_organizations():
    country = ConfigFile(government_forms={GovernmentForm.MAYOR_COUNCIL: FormConfig()})

    with pytest.raises(ValueError, match="mayor_council has no organizations"):
        merged_config(_COUNTRY_ROLES, country, None)


def test_an_organization_role_must_be_a_role():
    state = ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: FormConfig(
                organizations=[DerivedOrganization(name="Board of Aldermen", role_labels=["Alderman"])]
            )
        }
    )

    with pytest.raises(ValueError, match="Board of Aldermen's role 'Alderman' is not a role"):
        merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)


def test_an_organization_role_may_be_an_alias():
    state = ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: FormConfig(
                organizations=[DerivedOrganization(name="Council", role_labels=["Councilmember"])]
            )
        }
    )

    assert merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)


def test_without_state_forms_every_country_form_is_allowed():
    config = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, None)

    assert allowed_forms(config, "Springfield city") == [
        GovernmentForm.MAYOR_COUNCIL,
        GovernmentForm.COUNCIL_MANAGER,
        GovernmentForm.OPEN_TOWN_MEETING,
    ]


def test_a_suffixed_state_form_decides_only_names_with_that_suffix():
    state = ConfigFile(
        government_forms={GovernmentForm.OPEN_TOWN_MEETING: FormConfig(suffixes=["town"])}
    )
    config = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)

    assert allowed_forms(config, "Millbury town") == [GovernmentForm.OPEN_TOWN_MEETING]
    assert len(allowed_forms(config, "Worcester city")) == 3


def test_state_forms_without_suffixes_narrow_the_state():
    state = ConfigFile(government_forms={GovernmentForm.COUNCIL_MANAGER: FormConfig()})

    assert allowed_forms(merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state), "Springfield city") == [
        GovernmentForm.COUNCIL_MANAGER
    ]


def test_a_state_renames_a_forms_organizations():
    aldermen = DerivedOrganization(name="Board of Aldermen", role_labels=["Council Member"])
    state = ConfigFile(
        government_forms={GovernmentForm.MAYOR_COUNCIL: FormConfig(organizations=[aldermen])}
    )
    config = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)

    assert form_organizations(config, GovernmentForm.MAYOR_COUNCIL) == [aldermen]


def test_a_state_form_without_organizations_keeps_the_countrys():
    state = ConfigFile(
        government_forms={GovernmentForm.OPEN_TOWN_MEETING: FormConfig(suffixes=["town"])}
    )

    assert form_organizations(merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state), GovernmentForm.OPEN_TOWN_MEETING) == [
        _SELECT_BOARD
    ]


def test_a_saved_form_beats_the_rules():
    config = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, None)

    assert resolve_government_form(config, "Springfield city", GovernmentForm.COUNCIL_MANAGER) == (
        GovernmentForm.COUNCIL_MANAGER
    )


def test_one_allowed_form_decides_it_and_several_leave_it_unknown():
    state = ConfigFile(government_forms={GovernmentForm.OPEN_TOWN_MEETING: FormConfig(suffixes=["town"])})
    config = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, state)

    assert resolve_government_form(config, "Millbury town", None) == GovernmentForm.OPEN_TOWN_MEETING
    assert resolve_government_form(config, "Worcester city", None) is None


def test_no_organizations_until_the_form_is_known():
    assert derived_organizations(merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, None), None) == []


def test_a_form_saved_at_the_wrong_level_derives_nothing():
    config = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, None)

    assert derived_organizations(config, GovernmentForm.COUNTY_EXECUTIVE) == []


def test_a_known_form_derives_its_organizations():
    config = merged_config(_COUNTRY_ROLES, _COUNTRY_FORMS, None)

    assert derived_organizations(config, GovernmentForm.OPEN_TOWN_MEETING) == [_SELECT_BOARD]


def test_a_role_in_two_organizations_of_one_form_is_rejected():
    """Research files a role into the first organization that holds it."""
    country_forms = ConfigFile(
        government_forms={GovernmentForm.MAYOR_COUNCIL: FormConfig(organizations=[_COUNCIL, _COUNCIL])}
    )

    with pytest.raises(ValueError, match="'Council Member' is in two organizations"):
        merged_config(_COUNTRY_ROLES, country_forms, None)


def test_a_jurisdiction_takes_the_country_files_for_its_level_and_its_states_file():
    configs = {
        COUNTRY_ROLES_PATH: _COUNTRY_ROLES,
        "data_source/local/config.yml": _COUNTRY_FORMS,
        "data_source/ma/local/config.yml": ConfigFile(
            government_forms={GovernmentForm.OPEN_TOWN_MEETING: FormConfig(suffixes=["town"])}
        ),
    }

    massachusetts = jurisdiction_config(configs, "ma", JurisdictionLevel.LOCAL)
    washington = jurisdiction_config(configs, "wa", JurisdictionLevel.LOCAL)

    assert allowed_forms(massachusetts, "Millbury town") == [GovernmentForm.OPEN_TOWN_MEETING]
    assert len(allowed_forms(washington, "Millbury town")) == 3
