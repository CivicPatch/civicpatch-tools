import pytest

from core.organization_derivation import (
    merged_by_name,
    role_labels_by_organization,
    with_role_labels,
)
from shared.schemas import GoverningLawOrganizations, Role, RoleConfig
from shared.utils.government_forms import DerivedOrganization
from shared.utils.taxonomy import build_taxonomy

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
def test_each_organization_gets_the_role_labels_derived_under_its_name():
    derived = OPEN_TOWN_MEETING
    organizations = [
        {"id": "a", "name": "Select Board", "posts": []},
        {"id": "b", "name": "Town Meeting", "posts": []},
        {"id": "c", "name": "School Committee", "posts": []},
    ]

    labelled = with_role_labels(organizations, derived, {})

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


_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="member", label="Member", aliases=["Select Board Member", "Council Member", "Selectperson"]),
            Role(id="chair", label="Chair"),
            Role(id="vice-chair", label="Vice Chair"),
            Role(id="moderator", label="Moderator"),
            Role(id="mayor", label="Mayor"),
        ]
    )
)


def _answer(*posts: tuple[str, str, str]) -> GoverningLawOrganizations:
    source = {"url": "https://example.gov/charter", "note": "the quote", "extras": {"source_page_id": "p1", "matched_in": "sentence"}}
    return GoverningLawOrganizations.model_validate(
        {
            "posts": [{"role": role, "label": label, "organization_id": name, "sources": [source]} for name, role, label in posts],
            "extras": {"governing_law_collected_at": "2026-11-19T00:00:00Z"},
        }
    )


@pytest.mark.unit
def test_with_no_answer_from_the_law_every_role_the_form_gives_keeps_its_config_label():
    assert role_labels_by_organization(None, OPEN_TOWN_MEETING, _TAXONOMY) == {
        "Select Board": {"member": "Select Board Member", "chair": "Chair", "vice-chair": "Vice Chair"},
        "Town Meeting": {"moderator": "Moderator"},
    }


@pytest.mark.unit
def test_the_place_s_law_replaces_the_form_for_each_organization_it_quotes_and_only_those():
    answer = _answer(("Select Board", "member", "Selectperson"))

    assert role_labels_by_organization(answer, OPEN_TOWN_MEETING, _TAXONOMY) == {
        "Select Board": {"member": "Selectperson"},
        "Town Meeting": {"moderator": "Moderator"},
    }


@pytest.mark.unit
def test_a_charter_giving_the_mayor_an_office_of_their_own_takes_the_mayor_off_the_council():
    answer = _answer(("Council", "member", "Council Member"), ("Office of the Mayor", "mayor", "Mayor"))

    labels = role_labels_by_organization(answer, COUNCIL_MANAGER, _TAXONOMY)

    assert labels["Council"] == {"member": "Council Member"}
    assert labels["Office of the Mayor"] == {"mayor": "Mayor"}


@pytest.mark.unit
def test_the_pick_list_names_each_role_as_the_law_does_and_as_the_config_does():
    organizations = [{"id": "a", "name": "Select Board", "posts": []}]
    labels = role_labels_by_organization(_answer(("Select Board", "member", "Selectperson")), OPEN_TOWN_MEETING, _TAXONOMY)

    labelled = with_role_labels(organizations, OPEN_TOWN_MEETING, labels)

    assert labelled[0]["role_labels"] == ["Selectperson", "Select Board Member", "Chair", "Vice Chair"]
