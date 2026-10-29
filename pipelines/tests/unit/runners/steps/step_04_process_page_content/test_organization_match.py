"""The organization label matcher: the words settle it, say none, name several, or leave it to the model;
never a wrong name."""

from runners.pipeline03_people_collector.constants import MATCH_MAX_OUTPUT_TOKENS
import pathlib
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from pydantic import ValidationError

import services.open_router.prompts as open_router_prompts
from runners.pipeline03_people_collector.steps.step_04_process_page_content.organization_match import (
    ask_organization,
    OrganizationLabelMatch,
    match_by_words,
    match_response_schema,
    organization_by_label,
    organization_id_by_name,
    place_words,
    placed_name,
    position_words,
    resolve_organizations,
    shared_terms,
    with_role_aliases,
    without_default,
)
from shared.schemas import KnownOrganization, Role, RoleConfig, SelectionMethod
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

_CASES_FILE = pathlib.Path(__file__).parents[4] / "prompts/datasets/local/organization_match/cases.yml"
_CHOICES = ["Selectboard", "Board of Listers"]
_LISTERS = KnownOrganization(id="bl", name="Board of Listers", role_labels=["Lister"])
_TRUSTEES = KnownOrganization(id="bt", name="Board of Trustees", role_labels=["Trustee", "Village President"])
_PUBLIC_FUNDS = KnownOrganization(id="pf", name="Trustees of Public Funds", role_labels=["Trustee of Public Funds"])
_LIBRARY = KnownOrganization(id="lt", name="Board of Library Trustees", role_labels=["Library Trustee"])
_BOARD = KnownOrganization(id="b", name="Board", role_labels=["Supervisor", "Clerk", "Treasurer", "Trustee"])
_COUNCIL = KnownOrganization(id="c", name="Council", role_labels=["Council Member"])
_MAYOR = KnownOrganization(id="m", name="Office of the Mayor", role_labels=["Mayor"])
_TOWN_OFFICERS = KnownOrganization(id="to", name="Town Officers", role_labels=["Town Clerk"], meta_is_default=True)
_ASK = "runners.pipeline03_people_collector.steps.step_04_process_page_content.organization_match.ask_organization"


def _organizations(place: dict) -> list[KnownOrganization]:
    return [KnownOrganization(id=entry["name"], **entry) for entry in place["organizations"]]


def _cases() -> list[tuple[str, str, list[KnownOrganization], str]]:
    data = yaml.safe_load(_CASES_FILE.read_text())
    return [
        (case["organization_label"], data["places"][case["place"]]["name"], _organizations(data["places"][case["place"]]), case["expected"])
        for case in data["cases"]
    ]


def test_a_label_inside_one_vocabulary_is_that_organization():
    assert match_by_words("Lister Board", place_words([_LISTERS, _PUBLIC_FUNDS], _TAXONOMY, "Whiting town")) == OrganizationLabelMatch(names=["Board of Listers"])


def test_a_label_equal_to_a_name_matches_even_when_its_words_are_all_common():
    assert match_by_words("Township Board", place_words([_BOARD], _TAXONOMY, "Leighton township")).names == ["Board"]
    assert match_by_words("Mayor's Office", place_words([_MAYOR, _BOARD], _TAXONOMY, "Meridian city")).names == ["Office of the Mayor"]


def test_the_place_s_own_name_is_dropped_misspelt_or_not():
    assert match_by_words("Bellow Falls Village Trustees", place_words([_TRUSTEES], _TAXONOMY, "Bellows Falls village")).names == ["Board of Trustees"]


def test_a_label_sharing_no_word_is_none():
    assert match_by_words("Justices of the Peace", place_words([_LISTERS, _PUBLIC_FUNDS], _TAXONOMY, "Athens town")) == OrganizationLabelMatch()


def test_a_label_sharing_only_some_words_is_uncertain():
    assert match_by_words("Campbell Fund Trustees", place_words([_LISTERS, _PUBLIC_FUNDS], _TAXONOMY, "Athens town")).uncertain
    assert match_by_words("Saxtons River Village Trustees", place_words([_TRUSTEES], _TAXONOMY, "Bellows Falls village")).uncertain


def test_a_label_two_vocabularies_cover_together_names_both():
    assert match_by_words("Mayor & City Council", place_words([_COUNCIL, _MAYOR], _TAXONOMY, "Greenwood Village city")).names == ["Council", "Office of the Mayor"]


def test_a_label_inside_two_vocabularies_is_none_and_the_person_s_label_decides():
    assert match_by_words("Trustees", place_words([_PUBLIC_FUNDS, _LIBRARY], _TAXONOMY, "Athens town")) == OrganizationLabelMatch()


def test_the_default_is_never_a_candidate():
    assert match_by_words("Town Clerk", place_words([_LISTERS, _TOWN_OFFICERS], _TAXONOMY, "Athens town")) == OrganizationLabelMatch()


@pytest.mark.parametrize("organization, place_name, organizations, expected", _cases())
def test_the_words_never_give_a_wrong_answer_on_the_eval_cases(organization, place_name, organizations, expected):
    match = match_by_words(organization, place_words(organizations, _TAXONOMY, place_name))
    assert match.uncertain or match.names == ([] if expected == "none" else [expected])


def test_the_schema_accepts_a_choice_or_none_and_refuses_the_rest():
    schema = match_response_schema(_CHOICES)

    for organization in ("Selectboard", "none"):
        schema.model_validate({"organization": organization})
    with pytest.raises(ValidationError):
        schema.model_validate({"organization": "Planning Commission"})


@pytest.mark.asyncio
async def test_only_the_uncertain_parts_are_asked_once_each_and_a_joined_label_takes_its_first_match():
    ask = AsyncMock(return_value=[])

    with patch(_ASK, new=ask):
        resolved = await resolve_organizations(["Listers", "Campbell Fund Trustees", "Campbell Fund Trustees, Listers", "Justices of the Peace", "", None], "run", "ocdid", "Athens town", place_words([_LISTERS, _PUBLIC_FUNDS], _TAXONOMY, "Athens town"))

    assert resolved == {
        "Listers": ["Board of Listers"],
        "Campbell Fund Trustees": [],
        "Campbell Fund Trustees, Listers": ["Board of Listers"],
        "Justices of the Peace": [],
    }
    assert ask.await_count == 1


def test_among_several_bodies_a_label_names_the_person_s_own_label_chooses():
    resolved = {"Mayor & City Council": ["Council", "Office of the Mayor"]}

    assert placed_name("Mayor & City Council", "Mayor", resolved, place_words([_COUNCIL, _MAYOR], _TAXONOMY, "Greenwood Village city"), _TAXONOMY) == "Office of the Mayor"
    assert placed_name("Mayor & City Council", "Council Member District 1", resolved, place_words([_COUNCIL, _MAYOR], _TAXONOMY, "Greenwood Village city"), _TAXONOMY) == "Council"
    assert placed_name("Mayor & City Council", "Member", resolved, place_words([_COUNCIL, _MAYOR], _TAXONOMY, "Greenwood Village city"), _TAXONOMY) is None


def test_a_label_naming_one_organization_s_role_places_there():
    assert organization_by_label("Lister", [_LISTERS, _PUBLIC_FUNDS, _TOWN_OFFICERS], _TAXONOMY) == "Board of Listers"
    assert organization_by_label("Trustee", [_TRUSTEES, _PUBLIC_FUNDS], _TAXONOMY) is None
    assert organization_by_label("Town Clerk", [_LISTERS, _TOWN_OFFICERS], _TAXONOMY) is None


def test_a_name_becomes_its_id_and_no_name_becomes_no_id():
    assert organization_id_by_name("Board of Listers", [_LISTERS]) == "bl"
    assert organization_id_by_name(None, [_LISTERS]) is None


def test_the_question_names_the_place_the_label_and_every_choice_and_the_prompt_carries_the_rule():
    question = open_router_prompts.organization_match_question("Athens town", "Campbell Fund Trustees", _CHOICES)
    prompt = open_router_prompts.organization_match_prompt()

    assert '"Campbell Fund Trustees"' in question and "Athens town" in question
    for choice in [*_CHOICES, "none"]:
        assert f'"{choice}"' in question
    assert "a fund, a library, a building" in prompt and '"none"' in prompt


_SELECTBOARD = KnownOrganization(id="sb", name="Selectboard", role_labels=["Select Board Member", "Chair", "Vice Chair"])
_TOWN_MEETING = KnownOrganization(id="tm", name="Town Meeting", role_labels=["Moderator"])
_CEMETERY = KnownOrganization(id="cc", name="Board of Cemetery Commissioners", role_labels=["Cemetery Commissioner"])
_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="member", label="Member", aliases=["Select Board Member", "Selectmen", "Selectperson", "Commissioner", "Representative"]),
            Role(id="chair", label="Chair", selection_method=SelectionMethod.ELECTED_BY_MEMBERS, aliases=["Chairman"]),
            Role(id="vice-chair", label="Vice Chair", selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
            Role(id="clerk", label="Clerk", aliases=["Town Clerk"]),
            Role(id="mayor", label="Mayor"),
            Role(id="moderator", label="Moderator"),
            Role(id="lister", label="Lister"),
        ]
    )
)


def test_aliases_spelled_from_the_organization_s_words_join_its_vocabulary_and_broad_ones_do_not():
    widened = {organization.name: organization for organization in with_role_aliases([_SELECTBOARD, _CEMETERY], _TAXONOMY)}

    assert match_by_words("Board of Selectmen", place_words(list(widened.values()), _TAXONOMY, "Morgan town")).names == ["Selectboard"]
    assert "commissioner" not in [label.lower() for label in widened["Selectboard"].role_labels]


def test_a_label_containing_one_organization_s_role_label_names_it_whatever_else_it_says():
    assert match_by_words("Moderator (Town & School)", place_words([_SELECTBOARD, _TOWN_MEETING], _TAXONOMY, "Worcester town")).names == ["Town Meeting"]
    assert match_by_words("Cemetery Commissioners - 3 Years", place_words([_SELECTBOARD, _CEMETERY], _TAXONOMY, "Corinth town")).names == ["Board of Cemetery Commissioners"]


def test_a_label_of_position_words_only_names_none():
    assert match_by_words("Vice Chair", place_words([_SELECTBOARD, _TOWN_MEETING], _TAXONOMY, "Wilmington town")) == OrganizationLabelMatch()


def test_an_email_address_names_none():
    assert match_by_words("lister@westwindsorvt.org", place_words([_LISTERS, _SELECTBOARD], _TAXONOMY, "West Windsor town")) == OrganizationLabelMatch()


_TOWN_OFFICERS_FULL = KnownOrganization(
    id="to", name="Town Officers", role_labels=["Town Clerk", "Trustee of Public Money", "Town Manager"], meta_is_default=True
)


def test_a_label_that_is_an_office_of_the_default_names_none_without_asking():
    organizations = [_PUBLIC_FUNDS, _LIBRARY, _TOWN_OFFICERS_FULL]

    assert match_by_words("Trustee of Public Money", place_words(organizations, _TAXONOMY, "Cambridge town")) == OrganizationLabelMatch()


def test_a_label_naming_a_board_beside_a_default_office_is_still_open():
    assert match_by_words("Selectboard & Town Manager", place_words([_SELECTBOARD, _TOWN_OFFICERS_FULL], _TAXONOMY, "Proctor town")).uncertain


def test_a_name_and_a_position_name_none():
    assert match_by_words("Paul Warden, Chair", place_words([_SELECTBOARD, _TOWN_MEETING], _TAXONOMY, "Johnson town")) == OrganizationLabelMatch()


@pytest.mark.asyncio
async def test_the_matching_call_is_capped_below_the_default_output_limit():
    run_prompt = AsyncMock(return_value=match_response_schema(_CHOICES).model_validate({"organization": "none"}))

    with patch("runners.pipeline03_people_collector.steps.step_04_process_page_content.organization_match.open_router_llm.run_prompt", new=run_prompt):
        await ask_organization("run", "ocdid", "Athens town", "Campbell Fund Trustees", [_LISTERS, _PUBLIC_FUNDS])

    assert run_prompt.await_args is not None
    assert run_prompt.await_args.kwargs["max_output_tokens"] == MATCH_MAX_OUTPUT_TOKENS


def test_the_default_is_never_a_candidate_for_a_label():
    assert [organization.name for organization in without_default([_TOWN_OFFICERS, _LISTERS, _PUBLIC_FUNDS])] == [
        "Board of Listers",
        "Trustees of Public Funds",
    ]


_WATER = KnownOrganization(id="wc", name="Water Commissioners", role_labels=["Water Commissioner"])
_BUDGET = KnownOrganization(id="ab", name="Advisory Budget Committee", role_labels=["Advisory Budget Committee Member"])
_CITY_OFFICERS = KnownOrganization(id="co", name="City Officers", role_labels=["City Clerk"], meta_is_default=True)


def test_a_word_several_of_the_place_s_organizations_share_tells_none_of_them_apart():
    assert shared_terms([_CEMETERY, _WATER]) >= {"commissioner"}
    assert match_by_words("Commissioners", place_words([_CEMETERY, _WATER], _TAXONOMY, "Charleston town")) == OrganizationLabelMatch()


def test_the_kind_of_place_its_default_names_is_part_of_the_place_s_own_name():
    assert match_by_words("City Council", place_words([_COUNCIL, _MAYOR, _CITY_OFFICERS], _TAXONOMY, "Burlington")).names == ["Council"]


def test_a_stem_counts_as_the_word_it_starts():
    assert match_by_words("Cemetery Commission", place_words([_CEMETERY, _WATER], _TAXONOMY, "Athens town")).names == ["Board of Cemetery Commissioners"]


def test_a_word_for_a_kind_of_body_names_no_body():
    assert match_by_words("Committee Members", place_words([_BUDGET, _SELECTBOARD], _TAXONOMY, "Concord town")) == OrganizationLabelMatch()


def test_people_appointed_by_a_board_are_not_named_as_its_members():
    widened = with_role_aliases([_SELECTBOARD, _TOWN_MEETING], _TAXONOMY)

    assert match_by_words("Appointed by the Selectboard", place_words(widened, _TAXONOMY, "Orange town")).names != ["Selectboard"]


def test_a_role_of_no_candidate_beside_a_body_s_name_leaves_the_body_named():
    """"Clerk" is a taxonomy role but none of the Selectboard's own words: a clerk post on the Selectboard."""
    widened = with_role_aliases([_SELECTBOARD, _TOWN_MEETING], _TAXONOMY)

    assert match_by_words("Select Board Clerk", place_words(widened, _TAXONOMY, "Townshend town")).names == ["Selectboard"]


def test_position_words_come_from_the_roles_members_fill_not_from_a_list():
    positions = position_words(_TAXONOMY, [_SELECTBOARD, _TOWN_MEETING])

    assert {"chair", "vice", "member"} <= positions and "mayor" not in positions and "clerk" not in positions


def test_a_person_under_a_label_naming_no_body_is_placed_by_their_own_label():
    resolved = {"Contact Us": []}

    assert placed_name("Contact Us", "Lister", resolved, place_words([_LISTERS, _PUBLIC_FUNDS], _TAXONOMY, "Athens town"), _TAXONOMY) == "Board of Listers"
    assert placed_name(None, "Lister", {}, place_words([_LISTERS, _PUBLIC_FUNDS], _TAXONOMY, "Athens town"), _TAXONOMY) == "Board of Listers"
    assert placed_name("Contact Us", "Justice of the Peace", resolved, place_words([_LISTERS, _PUBLIC_FUNDS], _TAXONOMY, "Athens town"), _TAXONOMY) is None
