import pytest
from shared.schemas import GovernmentForm, JurisdictionLevel, Role, RoleConfig, RoleStatus
from shared.utils.government_forms import (
    GovernmentFormsConfig,
    CountyGovernment,
    DerivedOrganization,
    allowed_forms,
    derived_organizations,
    describe_government_form,
    load_government_forms_config,
    organizations_for,
    resolve_government_form,
)
from shared.utils.taxonomy import build_taxonomy


def _role(id_, label):
    return Role(id=id_, label=label, status=RoleStatus.ACTIVE, aliases=[], is_unique=False)


# Every role the derivation table may name. A label missing here is a label missing from the
# real taxonomy too, which is what 2c's data step exists to fix.
_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            _role("mayor", "Mayor"),
            _role("council-member", "Council Member"),
            _role("commissioner", "Commissioner"),
            _role("supervisor", "Supervisor"),
            _role("clerk", "Clerk"),
            _role("treasurer", "Treasurer"),
            _role("trustee", "Trustee"),
            _role("select-board-member", "Select Board Member"),
            _role("moderator", "Moderator"),
            _role("town-meeting-member", "Town Meeting Member"),
            _role("county-executive", "County Executive"),
            _role("chair", "Chair"),
            _role("vice-chair", "Vice Chair"),
            _role("council-president", "Council President"),
        ]
    )
)


def test_mayor_council_is_a_council_and_a_separate_mayor():
    organizations = organizations_for(GovernmentForm.MAYOR_COUNCIL)

    assert [(o.name, o.role_labels) for o in organizations] == [
        ("Council", ["Council Member"]),
        ("Office of the Mayor", ["Mayor"]),
    ]


def test_council_manager_puts_the_mayor_inside_the_council():
    organizations = organizations_for(GovernmentForm.COUNCIL_MANAGER)

    assert [(o.name, o.role_labels) for o in organizations] == [
        ("Council", ["Council Member", "Mayor"]),
    ]


def test_commission_is_one_body_with_the_mayor_in_it():
    organizations = organizations_for(GovernmentForm.COMMISSION)

    assert [(o.name, o.role_labels) for o in organizations] == [
        ("Commission", ["Commissioner", "Mayor"]),
    ]


def test_township_board_is_one_board_of_elected_officers():
    organizations = organizations_for(GovernmentForm.TOWNSHIP_BOARD)

    assert [(o.name, o.role_labels) for o in organizations] == [
        ("Board", ["Supervisor", "Clerk", "Treasurer", "Trustee"]),
    ]


def test_open_town_meeting_is_a_select_board_and_a_moderator():
    organizations = organizations_for(GovernmentForm.OPEN_TOWN_MEETING)

    assert [(o.name, o.role_labels) for o in organizations] == [
        ("Select Board", ["Select Board Member", "Chair", "Vice Chair"]),
        ("Town Meeting", ["Moderator"]),
    ]


def test_representative_town_meeting_adds_elected_members_to_town_meeting():
    open_form = organizations_for(GovernmentForm.OPEN_TOWN_MEETING)
    representative = organizations_for(GovernmentForm.REPRESENTATIVE_TOWN_MEETING)

    assert representative[0] == open_form[0]
    assert representative[1].role_labels == ["Moderator", "Town Meeting Member"]


def test_county_executive_is_a_council_and_a_separate_executive():
    organizations = organizations_for(GovernmentForm.COUNTY_EXECUTIVE)

    assert [(o.name, o.role_labels) for o in organizations] == [
        ("Council", ["Council Member"]),
        ("County Executive", ["County Executive"]),
    ]


@pytest.mark.parametrize("form", list(GovernmentForm))
def test_every_form_has_a_description(form):
    assert describe_government_form(form).startswith(form.value.replace("_", " ") + " (")


@pytest.mark.parametrize("form", list(GovernmentForm))
def test_no_role_belongs_to_two_organizations_of_one_form(form):
    """Research files a role into the first organization whose role labels hold it, which is
    only right while that organization is the only one."""
    seen: list[str] = []
    for organization in organizations_for(form):
        for label in organization.role_labels:
            assert label not in seen, f"{form}: {label!r} is in two organizations"
            seen.append(label)


@pytest.mark.parametrize("form", list(GovernmentForm))
def test_every_derived_role_label_resolves(form):
    for organization in organizations_for(form):
        for label in organization.role_labels:
            assert label in _TAXONOMY.role_ids, f"{form}: {label!r} is not a role"


_LOCAL = JurisdictionLevel.LOCAL
_COUNTIES = JurisdictionLevel.COUNTIES

_TN_COMMISSION = DerivedOrganization(name="County Commission", role_labels=["Commissioner"])
_TN_MAYOR = DerivedOrganization(name="Office of the County Mayor", role_labels=["Mayor"])
_WA_BOARD = DerivedOrganization(name="Board of County Commissioners", role_labels=["Commissioner"])

_CONFIG = GovernmentFormsConfig.model_validate(
    {
        "country": {
            "local": {"*": ["mayor_council", "council_manager", "township_board"]},
            "counties": {"*": ["commission", "county_executive"]},
        },
        "states": {
            "mi": {"local": {"township": ["township_board"]}},
            "tx": {"counties": {"*": ["commission"]}},
        },
        "county_governments": {
            "tn": CountyGovernment(board=_TN_COMMISSION, executive=_TN_MAYOR).model_dump(),
            "wa": CountyGovernment(board=_WA_BOARD).model_dump(),
        },
    }
)


def test_a_state_suffix_rule_decides_its_own_rows():
    assert allowed_forms(_CONFIG, "mi", _LOCAL, "Hayes township") == [GovernmentForm.TOWNSHIP_BOARD]


def test_a_state_rule_leaves_other_suffixes_to_the_country():
    forms = allowed_forms(_CONFIG, "mi", _LOCAL, "Detroit city")

    assert forms == [
        GovernmentForm.MAYOR_COUNCIL,
        GovernmentForm.COUNCIL_MANAGER,
        GovernmentForm.TOWNSHIP_BOARD,
    ]


def test_a_state_wildcard_covers_every_name_at_its_level():
    assert allowed_forms(_CONFIG, "tx", _COUNTIES, "Harris County") == [GovernmentForm.COMMISSION]


def test_a_state_with_no_entry_gets_the_country_forms():
    forms = allowed_forms(_CONFIG, "wa", _COUNTIES, "King County")

    assert forms == [GovernmentForm.COMMISSION, GovernmentForm.COUNTY_EXECUTIVE]


def test_state_level_has_no_forms():
    with pytest.raises(ValueError):
        allowed_forms(_CONFIG, "wa", JurisdictionLevel.STATE, "Washington")


def test_a_county_with_no_form_yet_gets_its_states_board():
    assert derived_organizations(_CONFIG, "wa", _COUNTIES, None) == [_WA_BOARD]


def test_a_commission_county_gets_only_its_board():
    assert derived_organizations(_CONFIG, "tn", _COUNTIES, GovernmentForm.COMMISSION) == [_TN_COMMISSION]


def test_a_county_executive_county_gets_its_states_executive():
    organizations = derived_organizations(_CONFIG, "tn", _COUNTIES, GovernmentForm.COUNTY_EXECUTIVE)

    assert organizations == [_TN_COMMISSION, _TN_MAYOR]


def test_a_state_with_no_executive_title_gets_county_executive():
    organizations = derived_organizations(_CONFIG, "wa", _COUNTIES, GovernmentForm.COUNTY_EXECUTIVE)

    assert [o.name for o in organizations] == ["Board of County Commissioners", "County Executive"]


def test_a_county_in_a_state_with_no_titles_gets_nothing():
    assert derived_organizations(_CONFIG, "ca", _COUNTIES, GovernmentForm.COMMISSION) == []


def test_a_local_jurisdiction_gets_its_forms_organizations():
    organizations = derived_organizations(_CONFIG, "wa", _LOCAL, GovernmentForm.COUNCIL_MANAGER)

    assert organizations == organizations_for(GovernmentForm.COUNCIL_MANAGER)


def test_a_local_jurisdiction_with_no_form_gets_nothing():
    assert derived_organizations(_CONFIG, "wa", _LOCAL, None) == []


def test_the_government_form_beats_a_rule():
    form = resolve_government_form(
        _CONFIG, "mi", _LOCAL, "Hayes township", GovernmentForm.COUNCIL_MANAGER
    )

    assert form == GovernmentForm.COUNCIL_MANAGER


def test_with_no_government_form_a_single_allowed_form_decides_it():
    form = resolve_government_form(_CONFIG, "mi", _LOCAL, "Hayes township", None)

    assert form == GovernmentForm.TOWNSHIP_BOARD


def test_with_no_government_form_several_allowed_forms_leave_it_unresolved():
    assert resolve_government_form(_CONFIG, "wa", _LOCAL, "Seattle city", None) is None


def test_a_state_may_not_allow_a_form_the_country_does_not():
    with pytest.raises(ValueError):
        GovernmentFormsConfig.model_validate(
            {
                "country": {"counties": {"*": ["commission"]}},
                "states": {"tx": {"counties": {"*": ["open_town_meeting"]}}},
            }
        )


def test_the_country_needs_a_wildcard_per_level():
    with pytest.raises(ValueError):
        GovernmentFormsConfig.model_validate(
            {"country": {"local": {"city": ["mayor_council"]}}}
        )


def test_the_shipped_config_loads():
    config = load_government_forms_config()

    assert allowed_forms(config, "ma", _LOCAL, "Millbury town") == [
        GovernmentForm.OPEN_TOWN_MEETING,
        GovernmentForm.REPRESENTATIVE_TOWN_MEETING,
    ]
    assert GovernmentForm.OPEN_TOWN_MEETING not in allowed_forms(
        config, "wa", _COUNTIES, "King County"
    )
    assert GovernmentForm.COUNTY_EXECUTIVE not in allowed_forms(
        config, "wa", _LOCAL, "Seattle city"
    )


def test_every_county_role_label_resolves():
    for state, government in load_government_forms_config().county_governments.items():
        organizations = [government.board]
        if government.executive is not None:
            organizations.append(government.executive)
        for organization in organizations:
            for label in organization.role_labels:
                assert label in _TAXONOMY.role_ids, f"{state}: {label!r} is not a role"
