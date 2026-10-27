import pytest

from core.organization_derivation import (
    default_organization_name,
    merged_by_name,
    with_role_labels,
)
from shared.utils.government_forms import DerivedOrganization

OPEN_TOWN_MEETING = [
    DerivedOrganization(name="Select Board", role_labels=["Select Board Member", "Chair", "Vice Chair"]),
    DerivedOrganization(name="Town Meeting", role_labels=["Moderator"]),
]
COUNCIL_MANAGER = [DerivedOrganization(name="Council", role_labels=["Council Member", "Mayor"])]
MAYOR_COUNCIL = [
    DerivedOrganization(name="Council", role_labels=["Council Member"]),
    DerivedOrganization(name="Office of the Mayor", role_labels=["Mayor"]),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    "jurisdiction_name, expected",
    [
        ("Essex town", "Town Officers"),
        ("Kitsap County", "County Officers"),
        ("Hyde Park village", "Village Officers"),
        ("Leighton township", "Township Officers"),
        ("Reno city (Lamar County)", "City Officers"),
        ("San Buenaventura (Ventura) city", "City Officers"),
        ("Princeton", "Officers"),
        ("Vermont", "Officers"),
        ("Fort Hall CDP", "Officers"),
    ],
)
def test_the_default_organization_is_named_after_the_legal_status(jurisdiction_name, expected):
    assert default_organization_name(jurisdiction_name) == expected


@pytest.mark.unit
def test_each_organization_gets_the_role_labels_derived_under_its_name():
    derived = OPEN_TOWN_MEETING
    organizations = [
        {"id": "a", "name": "Select Board", "posts": []},
        {"id": "b", "name": "Town Meeting", "posts": []},
        {"id": "c", "name": "School Committee", "posts": []},
    ]

    labelled = with_role_labels(organizations, derived)

    assert [o["role_labels"] for o in labelled] == [
        ["Select Board Member", "Chair", "Vice Chair"],
        ["Moderator"],
        [],
    ]
    assert "role_labels" not in organizations[0]


@pytest.mark.unit
def test_an_unknown_forms_organizations_merge_by_name_with_every_forms_labels():
    representative = [
        DerivedOrganization(name="Select Board", role_labels=["Select Board Member", "Chair", "Vice Chair"]),
        DerivedOrganization(name="Town Meeting", role_labels=["Moderator", "Town Meeting Member"]),
    ]

    merged = merged_by_name([OPEN_TOWN_MEETING, representative])

    assert merged == [
        DerivedOrganization(name="Select Board", role_labels=["Select Board Member", "Chair", "Vice Chair"]),
        DerivedOrganization(name="Town Meeting", role_labels=["Moderator", "Town Meeting Member"]),
    ]


@pytest.mark.unit
def test_merging_keeps_organizations_only_one_form_has():
    assert [o.name for o in merged_by_name([MAYOR_COUNCIL, COUNCIL_MANAGER])] == ["Council", "Office of the Mayor"]
    assert merged_by_name([MAYOR_COUNCIL, COUNCIL_MANAGER])[0].role_labels == ["Council Member", "Mayor"]
