"""Placement of one scraped person: the rules settle what they can; Jev, then the model, the rest."""

from unittest.mock import AsyncMock, patch

import pytest

import services.open_router.prompts as open_router_prompts
from runners.pipeline03_people_collector.constants import MATCH_MAX_OUTPUT_TOKENS
from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content.organization_match import (
    match_response_schema,
    place_words,
    with_role_aliases,
)
from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content.person_placement import (
    PageHeadings,
    RulePlacement,
    page_headings,
    placed_by_rules,
    placed_names,
)
from services.open_router.decisions import ChoiceAnswer
from shared.schemas import KnownOrganization, Role, RoleConfig, SelectionMethod
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

_MODULE = "runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02c_process_page_content.person_placement"
_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="member", label="Member", aliases=["Select Board Member"]),
            Role(id="chair", label="Chair", selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
            Role(id="vice-chair", label="Vice Chair", selection_method=SelectionMethod.ELECTED_BY_MEMBERS),
            Role(id="clerk", label="Clerk", aliases=["Town Clerk", "Village Clerk"]),
            Role(id="treasurer", label="Treasurer", aliases=["Town Treasurer", "Village Treasurer"]),
            Role(id="moderator", label="Moderator"),
            Role(id="mayor", label="Mayor"),
            Role(id="lister", label="Lister"),
            Role(id="road-commissioner", label="Road Commissioner"),
            Role(id="library-trustee", label="Library Trustee"),
            Role(id="trustee", label="Trustee"),
        ]
    )
)
_SELECTBOARD = KnownOrganization(id="sb", name="Selectboard", role_labels=["Select Board Member", "Chair", "Vice Chair"])
_TOWN_MEETING = KnownOrganization(id="tm", name="Town Meeting", role_labels=["Moderator"])
_TOWN_OFFICERS = KnownOrganization(id="to", name="Town Officers", role_labels=["Town Clerk", "Town Treasurer"], meta_is_default=True)
_TRUSTEES = KnownOrganization(id="bt", name="Board of Trustees", role_labels=["Trustee"])
_VILLAGE_OFFICERS = KnownOrganization(id="vo", name="Village Officers", role_labels=["Village Clerk", "Village Treasurer"], meta_is_default=True)
_COUNCIL = KnownOrganization(id="c", name="Council", role_labels=["Council Member"])
_MAYOR = KnownOrganization(id="m", name="Office of the Mayor", role_labels=["Mayor"])
_LISTERS = KnownOrganization(id="bl", name="Board of Listers", role_labels=["Lister"])
_TOWN = [_SELECTBOARD, _TOWN_MEETING, _TOWN_OFFICERS]
_NO_HEADINGS = PageHeadings()


def _rules(organization_label, label, organizations=_TOWN, place_name="Georgia town") -> RulePlacement:
    place = place_words(with_role_aliases(organizations, _TAXONOMY), _TAXONOMY, place_name)
    return placed_by_rules(organization_label, label, place, _TAXONOMY)


def test_a_page_s_title_and_first_heading_are_read_and_missing_ones_are_none():
    html = "<html><head><title> Selectboard | Hinesburg, VT </title></head><body><h1>Selectboard</h1><h1>Other</h1></body></html>"

    assert page_headings(html) == PageHeadings(title="Selectboard | Hinesburg, VT", first_heading="Selectboard")
    assert page_headings("<p>no headings</p>") == PageHeadings()


def test_a_member_of_a_board_the_town_does_not_have_goes_to_the_default_not_to_the_selectboard():
    assert _rules("Library Board of Trustees", "Library Trustee Chair") == RulePlacement(settled=True, name="Town Officers")


def test_a_bare_member_under_a_heading_naming_no_body_is_left_to_the_models():
    assert _rules("Library Board of Trustees", "Member") == RulePlacement(settled=False)


def test_an_officer_listed_under_a_board_s_heading_goes_to_the_default():
    village = [_TRUSTEES, _VILLAGE_OFFICERS]

    assert _rules("Board of Trustees", "Treasurer", village, place_name="Barton village") == RulePlacement(settled=True, name="Village Officers")


def test_a_role_one_listed_body_holds_places_there_whatever_the_heading_says():
    assert _rules(None, "Town Moderator") == RulePlacement(settled=True, name="Town Meeting")
    assert _rules("Mayor & City Council", "Mayor", [_COUNCIL, _MAYOR], place_name="Greenwood Village city").name == "Office of the Mayor"
    assert _rules("Contact Us", "Lister", [_LISTERS, _TOWN_OFFICERS], place_name="Athens town").name == "Board of Listers"


def test_a_seat_on_a_board_beside_an_officer_role_places_on_the_board():
    assert _rules(None, "Select Board Member and Road Commissioner").name == "Selectboard"


def test_a_bare_position_with_no_organization_label_is_left_to_the_models_whatever_the_page_is_called():
    assert _rules(None, "Vice Chair", place_name="Hinesburg town") == RulePlacement(settled=False)


@pytest.mark.asyncio
async def test_what_the_rules_settle_asks_no_model():
    with patch(f"{_MODULE}.decisions.choose", new=AsyncMock()) as choose, patch(f"{_MODULE}.open_router_llm.run_prompt", new=AsyncMock()) as run_prompt:
        names = await placed_names([(None, "Town Moderator")], _TOWN, _TAXONOMY, _NO_HEADINGS, "run", "ocd-jurisdiction/country:us/state:vt/place:georgia/government", "Georgia town", "https://x.gov")

    assert names == ["Town Meeting"]
    choose.assert_not_awaited()
    run_prompt.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_sure_jev_decides_once_per_distinct_person_and_the_model_is_not_asked():
    choose = AsyncMock(return_value=ChoiceAnswer(choice="Selectboard", confidence=0.9))
    people = [("Board", "Member"), ("Board", "Member")]

    with patch(f"{_MODULE}.decisions.choose", new=choose), patch(f"{_MODULE}.open_router_llm.run_prompt", new=AsyncMock()) as run_prompt:
        names = await placed_names(people, _TOWN, _TAXONOMY, _NO_HEADINGS, "run", "ocd-jurisdiction/country:us/state:vt/place:georgia/government", "Georgia town", "https://x.gov")

    assert names == ["Selectboard", "Selectboard"]
    assert choose.await_count == 1
    run_prompt.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unsure_jev_hands_the_person_to_the_capped_model_whose_none_is_no_organization():
    choose = AsyncMock(return_value=ChoiceAnswer(choice="Selectboard", confidence=0.3))
    run_prompt = AsyncMock(return_value=match_response_schema(["Selectboard", "Town Meeting"]).model_validate({"organization": "none"}))

    with patch(f"{_MODULE}.decisions.choose", new=choose), patch(f"{_MODULE}.open_router_llm.run_prompt", new=run_prompt):
        names = await placed_names([("Board", "Member")], _TOWN, _TAXONOMY, _NO_HEADINGS, "run", "ocd-jurisdiction/country:us/state:vt/place:georgia/government", "Georgia town", "https://x.gov")

    assert names == [None]
    assert run_prompt.await_args is not None
    assert run_prompt.await_args.kwargs["max_output_tokens"] == MATCH_MAX_OUTPUT_TOKENS


def test_the_question_names_the_place_the_page_both_labels_and_every_choice():
    question = open_router_prompts.person_organization_question(
        "Georgia town", "Library | Georgia", "Library Trustees", "Library Board of Trustees", "Member", ["Selectboard", "Town Meeting"]
    )
    criteria = open_router_prompts.person_organization_criteria(["Selectboard", "Town Meeting"])

    for text in ["Georgia town", '"Library | Georgia"', '"Library Trustees"', '"Library Board of Trustees"', '"Member"', '"Selectboard"', '"none"']:
        assert text in question
    assert set(criteria) == {"Selectboard", "Town Meeting", "none"}
    assert "a fund, a library, a building" in open_router_prompts.person_organization_prompt()
