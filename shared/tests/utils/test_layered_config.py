import pytest
from pydantic import ValidationError
from shared.schemas import GovernmentForm, JurisdictionLevel, SelectionMethod
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import (
    CharterLinkList,
    Classification,
    ConfigFile,
    ConfigRole,
    GoverningLawConfig,
    GovernmentFormConfig,
    allowed_classifications,
    allowed_government_forms,
    check_roles_distinct_across,
    config_path_layer,
    derived_organizations,
    every_role,
    jurisdiction_roles,
    government_form_organizations,
    jurisdiction_config,
    level_government_forms,
    merged_config,
    resolve_classification,
    resolve_government_form,
)

_COUNCIL = DerivedOrganization(name="Council", role_labels=["Council Member"])
_SELECT_BOARD = DerivedOrganization(name="Select Board", role_labels=["Select Board Member"])

_LEVEL = ConfigFile(
    roles=[
        ConfigRole(id="mayor", label="Mayor", is_unique=True),
        ConfigRole(id="council-member", label="Council Member", aliases=["councilmember"]),
        ConfigRole(id="select-board-member", label="Select Board Member"),
    ],
    government_forms={
        GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(organizations=[_COUNCIL]),
        GovernmentForm.COUNCIL_MANAGER: GovernmentFormConfig(organizations=[_COUNCIL]),
        GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(organizations=[_SELECT_BOARD]),
    },
)


def _level_with_forms(government_forms: dict) -> ConfigFile:
    return _LEVEL.model_copy(update={"government_forms": government_forms})


def test_state_roles_follow_the_level_roles_in_priority():
    state = ConfigFile(roles=[ConfigRole(id="assessor", label="Assessor")])

    roles = merged_config(_LEVEL, state).roles.roles

    assert [(role.id, role.priority) for role in roles] == [
        ("mayor", 0),
        ("council-member", 1),
        ("select-board-member", 2),
        ("assessor", 3),
    ]


def test_a_role_without_a_selection_method_is_popularly_elected():
    roles = merged_config(_LEVEL, None).roles.roles

    assert {role.selection_method for role in roles} == {SelectionMethod.ELECTED_BY_VOTERS}


def test_a_roles_selection_method_carries_into_the_merged_config():
    state = ConfigFile(roles=[ConfigRole(id="vice-mayor", label="Vice Mayor", selection_method=SelectionMethod.ELECTED_BY_MEMBERS)])

    roles = merged_config(_LEVEL, state).roles.roles

    assert roles[-1].selection_method == SelectionMethod.ELECTED_BY_MEMBERS


def test_no_state_file_is_the_country_alone():
    assert [role.id for role in merged_config(_LEVEL, None).roles.roles] == [
        "mayor",
        "council-member",
        "select-board-member",
    ]


def test_a_state_cannot_redefine_a_country_role():
    state = ConfigFile(roles=[ConfigRole(id="mayor", label="Town Mayor")])

    with pytest.raises(ValueError, match="'mayor' is listed twice"):
        merged_config(_LEVEL, state)


def test_a_state_alias_cannot_name_a_country_role():
    state = ConfigFile(roles=[ConfigRole(id="alderperson", label="Alderperson", aliases=["Council-Member"])])

    with pytest.raises(ValueError, match="names both 'council-member' and 'alderperson'"):
        merged_config(_LEVEL, state)


def test_role_aliases_stay_out_of_a_levels_file():
    level = _LEVEL.model_copy(update={"role_aliases": {"mayor": ["Burgess"]}})

    with pytest.raises(ValueError, match="role_aliases belong in a state's file"):
        merged_config(level, None)


def test_a_state_alias_adds_to_a_level_role():
    state = ConfigFile(role_aliases={"council-member": ["Assistant Judge"]})

    roles = {role.id: role for role in merged_config(_LEVEL, state).roles.roles}

    assert roles["council-member"].aliases == ["councilmember", "Assistant Judge"]


def test_a_state_alias_applies_only_in_that_state():
    configs = {
        "data_source/local/config.yml": _LEVEL,
        "data_source/vt/local/config.yml": ConfigFile(role_aliases={"council-member": ["Assistant Judge"]}),
    }

    def aliases(state: str) -> list[str]:
        roles = jurisdiction_config(configs, state, JurisdictionLevel.LOCAL).roles.roles
        return next(role.aliases for role in roles if role.id == "council-member")

    assert "Assistant Judge" in aliases("vt")
    assert "Assistant Judge" not in aliases("or")


def test_a_state_alias_must_name_a_level_role():
    state = ConfigFile(role_aliases={"assistant-judge": ["side judge"]})

    with pytest.raises(ValueError, match="role_aliases name no role of this level: \\['assistant-judge'\\]"):
        merged_config(_LEVEL, state)


_VT_COUNTY = "ocd-jurisdiction/country:us/state:vt/county:addison/government"
_VT_TOWN = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_TWO_LEVELS = {
    "data_source/local/config.yml": ConfigFile(roles=[ConfigRole(id="member", label="Member", aliases=["Select Board Member"])]),
    "data_source/counties/config.yml": ConfigFile(roles=[ConfigRole(id="member", label="Member", aliases=["County Commissioner"])]),
    "data_source/vt/counties/config.yml": ConfigFile(role_aliases={"member": ["Assistant Judge"]}),
}


def test_a_jurisdiction_gets_its_own_levels_and_states_roles():
    county = jurisdiction_roles(_TWO_LEVELS, _VT_COUNTY)
    town = jurisdiction_roles(_TWO_LEVELS, _VT_TOWN)

    assert county[0].aliases == ["County Commissioner", "Assistant Judge"]
    assert town[0].aliases == ["Select Board Member"]


def test_a_states_own_government_has_no_roles():
    assert jurisdiction_roles(_TWO_LEVELS, "ocd-jurisdiction/country:us/state:vt/government") == []


def test_every_role_is_one_role_per_id_with_every_files_aliases():
    roles = every_role(_TWO_LEVELS)

    assert [role.id for role in roles] == ["member"]
    assert roles[0].aliases == ["County Commissioner", "Select Board Member", "Assistant Judge"]


def test_each_level_has_its_own_roles_under_one_id():
    configs = {
        "data_source/local/config.yml": ConfigFile(roles=[ConfigRole(id="member", label="Member", aliases=["Select Board Member"])]),
        "data_source/counties/config.yml": ConfigFile(roles=[ConfigRole(id="member", label="Member", aliases=["County Commissioner"])]),
    }

    local = jurisdiction_config(configs, "vt", JurisdictionLevel.LOCAL).roles.roles
    counties = jurisdiction_config(configs, "vt", JurisdictionLevel.COUNTIES).roles.roles

    assert local[0].aliases == ["Select Board Member"]
    assert counties[0].aliases == ["County Commissioner"]


def test_two_states_may_share_an_alias():
    """They never merge for one jurisdiction, so the alias names one role wherever it is read."""
    tennessee = ConfigFile(roles=[ConfigRole(id="county-mayor", label="County Mayor", aliases=["executive"])])
    hawaii = ConfigFile(roles=[ConfigRole(id="county-executive", label="County Executive", aliases=["executive"])])

    check_roles_distinct_across([_LEVEL, tennessee, hawaii])


def test_two_states_still_cannot_share_a_label():
    tennessee = ConfigFile(roles=[ConfigRole(id="county-mayor", label="County Mayor")])
    hawaii = ConfigFile(roles=[ConfigRole(id="county-mayor-hi", label="County Mayor")])

    with pytest.raises(ValueError, match="names both 'county-mayor' and 'county-mayor-hi'"):
        check_roles_distinct_across([_LEVEL, tennessee, hawaii])


def test_one_file_may_not_give_two_roles_one_alias():
    with pytest.raises(ValidationError, match="'presiding officer' is an alias of both 'chair' and 'president'"):
        ConfigFile(
            roles=[
                ConfigRole(id="chair", label="Chair", aliases=["presiding officer"]),
                ConfigRole(id="president", label="President", aliases=["presiding officer"]),
            ]
        )


def test_a_state_alias_may_not_repeat_a_country_alias():
    state = ConfigFile(roles=[ConfigRole(id="alderperson", label="Alderperson", aliases=["councilmember"])])

    with pytest.raises(ValueError, match="'councilmember' is an alias of both 'council-member' and 'alderperson'"):
        merged_config(_LEVEL, state)


def test_an_alias_may_not_be_another_roles_label():
    with pytest.raises(ValidationError, match="'chair' names both 'chair' and 'president'"):
        ConfigFile(
            roles=[
                ConfigRole(id="chair", label="Chair"),
                ConfigRole(id="president", label="President", aliases=["chair"]),
            ]
        )


def test_a_state_form_must_be_a_country_form():
    state = ConfigFile(government_forms={GovernmentForm.COMMISSION: GovernmentFormConfig()})

    with pytest.raises(ValueError, match="commission is not a government form at this level"):
        merged_config(_LEVEL, state)


_TRUSTEES = DerivedOrganization(name="Board of Trustees", role_labels=["Council Member"])


def test_a_state_may_define_a_form_of_its_own_with_its_organizations():
    state = ConfigFile(
        government_forms={GovernmentForm.VILLAGE_BOARD: GovernmentFormConfig(suffixes=["village"], organizations=[_TRUSTEES])}
    )
    config = merged_config(_LEVEL, state)

    assert allowed_government_forms(config, "Hyde Park village") == [GovernmentForm.VILLAGE_BOARD]
    assert derived_organizations(config, GovernmentForm.VILLAGE_BOARD) == [_TRUSTEES]
    assert GovernmentForm.VILLAGE_BOARD in level_government_forms(config)


def test_a_states_own_form_is_offered_nowhere_else():
    config = merged_config(_LEVEL, None)

    assert GovernmentForm.VILLAGE_BOARD not in level_government_forms(config)
    assert derived_organizations(config, GovernmentForm.VILLAGE_BOARD) == []


def test_a_country_form_needs_organizations():
    level = _level_with_forms({GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig()})

    with pytest.raises(ValueError, match="level government form mayor_council has no organizations"):
        merged_config(level, None)


def test_an_organization_role_must_be_a_role():
    state = ConfigFile(
        government_forms={
            GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(
                organizations=[DerivedOrganization(name="Board of Aldermen", role_labels=["Alderman"])]
            )
        }
    )

    with pytest.raises(ValueError, match="Board of Aldermen's role 'Alderman' is not a role's label"):
        merged_config(_LEVEL, state)


def test_without_state_forms_every_country_form_is_allowed():
    config = merged_config(_LEVEL, None)

    assert allowed_government_forms(config, "Springfield city") == [
        GovernmentForm.MAYOR_COUNCIL,
        GovernmentForm.COUNCIL_MANAGER,
        GovernmentForm.OPEN_TOWN_MEETING,
    ]


def test_a_suffixed_state_form_decides_only_names_with_that_suffix():
    state = ConfigFile(
        government_forms={GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(suffixes=["town"])}
    )
    config = merged_config(_LEVEL, state)

    assert allowed_government_forms(config, "Millbury town") == [GovernmentForm.OPEN_TOWN_MEETING]
    assert len(allowed_government_forms(config, "Worcester city")) == 3


def test_state_forms_without_suffixes_narrow_the_state():
    state = ConfigFile(government_forms={GovernmentForm.COUNCIL_MANAGER: GovernmentFormConfig()})

    assert allowed_government_forms(merged_config(_LEVEL, state), "Springfield city") == [
        GovernmentForm.COUNCIL_MANAGER
    ]


def test_a_state_renames_a_forms_organizations():
    aldermen = DerivedOrganization(name="Board of Aldermen", role_labels=["Council Member"])
    state = ConfigFile(
        government_forms={GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(organizations=[aldermen])}
    )
    config = merged_config(_LEVEL, state)

    assert government_form_organizations(config, GovernmentForm.MAYOR_COUNCIL) == [aldermen]


def test_a_state_form_without_organizations_keeps_the_countrys():
    state = ConfigFile(
        government_forms={GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(suffixes=["town"])}
    )

    assert government_form_organizations(merged_config(_LEVEL, state), GovernmentForm.OPEN_TOWN_MEETING) == [
        _SELECT_BOARD
    ]


def test_a_saved_form_beats_the_rules():
    config = merged_config(_LEVEL, None)

    assert resolve_government_form(config, "Springfield city", GovernmentForm.COUNCIL_MANAGER) == (
        GovernmentForm.COUNCIL_MANAGER
    )


def test_one_allowed_form_decides_it_and_several_leave_it_unknown():
    state = ConfigFile(government_forms={GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(suffixes=["town"])})
    config = merged_config(_LEVEL, state)

    assert resolve_government_form(config, "Millbury town", None) == GovernmentForm.OPEN_TOWN_MEETING
    assert resolve_government_form(config, "Worcester city", None) is None


def test_no_organizations_until_the_form_is_known():
    assert derived_organizations(merged_config(_LEVEL, None), None) == []


def test_a_form_saved_at_the_wrong_level_derives_nothing():
    config = merged_config(_LEVEL, None)

    assert derived_organizations(config, GovernmentForm.COUNTY_EXECUTIVE) == []


def test_a_known_form_derives_its_organizations():
    config = merged_config(_LEVEL, None)

    assert derived_organizations(config, GovernmentForm.OPEN_TOWN_MEETING) == [_SELECT_BOARD]


def test_a_role_in_two_organizations_of_one_form_is_rejected():
    """Research files a role into the first organization that holds it."""
    level = _level_with_forms({GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(organizations=[_COUNCIL, _COUNCIL])})

    with pytest.raises(ValueError, match="'Council Member' is in two organizations"):
        merged_config(level, None)


def test_a_jurisdiction_takes_its_levels_file_and_its_states_file():
    configs = {
        "data_source/local/config.yml": _LEVEL,
        "data_source/ma/local/config.yml": ConfigFile(
            government_forms={GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(suffixes=["town"])}
        ),
    }

    massachusetts = jurisdiction_config(configs, "ma", JurisdictionLevel.LOCAL)
    washington = jurisdiction_config(configs, "wa", JurisdictionLevel.LOCAL)

    assert allowed_government_forms(massachusetts, "Millbury town") == [GovernmentForm.OPEN_TOWN_MEETING]
    assert len(allowed_government_forms(washington, "Millbury town")) == 3


def test_allowed_forms_come_back_in_the_enums_order_whatever_the_file_order():
    """Stored config is jsonb, which does not keep key order."""
    level = _level_with_forms(
        {
            GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(organizations=[_SELECT_BOARD]),
            GovernmentForm.MAYOR_COUNCIL: GovernmentFormConfig(organizations=[_COUNCIL]),
        }
    )

    assert allowed_government_forms(merged_config(level, None), "Springfield city") == [
        GovernmentForm.MAYOR_COUNCIL,
        GovernmentForm.OPEN_TOWN_MEETING,
    ]


_VERMONT_GOVERNING_LAW = {
    "charter_terms": ["Charter"],
    "charter_link_list": {
        "url": "https://legislature.vermont.gov/statutes/title/24APPENDIX",
        "title": "Chapter {*} : {lsad} of {place}",
        "text_link": {"old": "/statutes/chapter/", "new": "/statutes/fullchapter/"},
    },
    "classifications": {
        "town": {
            "lsad": ["town", "city"],
            "governed_by": "charter_or_general_law",
            "general_law": ["https://legislature.vermont.gov/statutes/section/17/055/02646"],
        },
        "village": {
            "lsad": ["village"],
            "governed_by": "charter_or_general_law",
            "general_law": ["https://legislature.vermont.gov/statutes/section/24/039/01304"],
        },
    },
}

# "city" cannot tell a home-rule city from a Type A one, so neither lists it.
_TEXAS_GOVERNING_LAW = GoverningLawConfig(
    charter_terms=["Home Rule Charter", "Charter"],
    classifications={
        "home_rule": Classification(governed_by="charter"),
        "type_a": Classification(governed_by="general_law", general_law=["https://statutes.capitol.texas.gov/Docs/LG/htm/LG.22.htm"]),
    },
)


def test_a_state_file_carries_its_governing_law_into_the_merge():
    state = ConfigFile.model_validate({"governing_law": _VERMONT_GOVERNING_LAW})

    governing_law = merged_config(_LEVEL, state).governing_law

    assert governing_law == GoverningLawConfig.model_validate(_VERMONT_GOVERNING_LAW)


def test_an_lsad_allows_the_classifications_that_list_it():
    governing_law = GoverningLawConfig.model_validate(_VERMONT_GOVERNING_LAW)

    assert allowed_classifications(governing_law, "Stowe town") == ["town"]
    assert allowed_classifications(governing_law, "Woodstock village") == ["village"]
    assert allowed_classifications(governing_law, "Unknown gore") == []


def test_one_allowed_classification_decides_it_and_none_leaves_it_unknown():
    governing_law = GoverningLawConfig.model_validate(_VERMONT_GOVERNING_LAW)

    assert resolve_classification(governing_law, "Stowe town", None) == "town"
    assert resolve_classification(_TEXAS_GOVERNING_LAW, "Abbott city", None) is None


def test_a_saved_classification_beats_the_lsad():
    assert resolve_classification(_TEXAS_GOVERNING_LAW, "Abbott city", "type_a") == "type_a"


def test_an_lsad_is_in_one_classification():
    with pytest.raises(ValidationError, match="lsad 'town' is in two classifications"):
        GoverningLawConfig(
            charter_terms=["Charter"],
            classifications={
                "town": Classification(lsad=["town"], governed_by="general_law"),
                "city": Classification(lsad=["town", "city"], governed_by="general_law"),
            },
        )


def test_governing_law_stays_out_of_a_levels_file():
    level = _LEVEL.model_copy(update={"governing_law": GoverningLawConfig(charter_terms=["Charter"])})

    with pytest.raises(ValueError, match="governing law belongs in a state's file"):
        merged_config(level, None)


def test_each_level_takes_its_own_states_governing_law():
    local_law = GoverningLawConfig(charter_terms=["Charter"])
    county_law = GoverningLawConfig(charter_terms=["County Charter"])
    configs = {
        "data_source/local/config.yml": _LEVEL,
        "data_source/counties/config.yml": _LEVEL,
        "data_source/tx/local/config.yml": ConfigFile(governing_law=local_law),
        "data_source/tx/counties/config.yml": ConfigFile(governing_law=county_law),
    }

    assert jurisdiction_config(configs, "tx", JurisdictionLevel.LOCAL).governing_law == local_law
    assert jurisdiction_config(configs, "tx", JurisdictionLevel.COUNTIES).governing_law == county_law


def test_a_charter_index_title_names_the_place():
    with pytest.raises(ValidationError, match="has no {place}"):
        CharterLinkList(url="https://example.gov/charters", title="{lsad} charter")



def test_a_forms_role_label_may_be_an_alias_of_a_role():
    level = ConfigFile(
        roles=[ConfigRole(id="member", label="Member", aliases=["Select Board Member"])],
        government_forms={
            GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
                organizations=[DerivedOrganization(name="Select Board", role_labels=["Select Board Member"])]
            )
        }
    )

    assert merged_config(level, None).level_government_forms[GovernmentForm.OPEN_TOWN_MEETING].organizations[0].role_labels == ["Select Board Member"]


@pytest.mark.parametrize(
    ("path", "layer"),
    [
        ("data_source/vt/local/config.yml", ("vt", JurisdictionLevel.LOCAL)),
        ("data_source/local/config.yml", (None, JurisdictionLevel.LOCAL)),
        ("data_source/wa/counties/config.yml", ("wa", JurisdictionLevel.COUNTIES)),
        ("data_source/config.yml", None),
        ("data_source/vt/local/place_essex.yml", None),
    ],
)
def test_a_config_path_names_the_state_and_level_it_governs(path, layer):
    assert config_path_layer(path) == layer
