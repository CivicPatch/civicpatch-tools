"""One extraction per page, each person stamped with the organization their organization label names."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runners.pipeline03_people_collector.schemas import (
    ExtractedPersonRecord,
    Link,
    LinkStatus,
    PeopleArrayLLMResponseSchema,
    ProcessPageContentStep,
)
from runners.pipeline03_people_collector.steps.step_04_process_page_content.heuristics_failure import (
    HeuristicsFailure,
)
from runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content import (
    collect_page_records,
)
from shared.schemas import KnownOrganization, Post
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_PAGE = Link(url="https://seattle.gov/elected-officials", status=LinkStatus.PREPROCESSED.value)
_CONTENT = "Elected officials: Mayor Katie Wilson. Council Member District 1: Rob Saka."
_RUN_PROMPT = (
    "runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content"
    ".open_router_llm.run_prompt"
)


def _organization(organization_id: str, name: str, labels: list[str]) -> KnownOrganization:
    posts = [
        Post(
            id=f"{organization_id}-{label}",
            jurisdiction_ocdid=_OCDID,
            organization_id=organization_id,
            role_id="role",
            division_ocdid="ocd-division/country:us/state:wa/place:seattle",
            label=label,
            role_label=label,
        )
        for label in labels
    ]
    return KnownOrganization(id=organization_id, name=name, posts=posts)


_COUNCIL = _organization("council", "City Council", ["Council Member District 1"])
_MAYOR = _organization("mayor", "Office of the Mayor", ["Mayor"])


def _answer(*people: tuple[str, str]) -> PeopleArrayLLMResponseSchema:
    return PeopleArrayLLMResponseSchema(
        people=[ExtractedPersonRecord(name=name, label=label) for name, label in people]
    )


async def _collect(organizations: list[KnownOrganization]):
    return await collect_page_records(
        pipeline_run_context_factory(steps={}),
        _PAGE,
        _CONTENT,
        organizations,
        [],
        ProcessPageContentStep(records={}),
        {},
        MagicMock(),
    )


def _picked(*people: tuple[str, str, str]):
    """An answer whose people each carry the organization the page listed them under, as written."""
    return PeopleArrayLLMResponseSchema.model_validate(
        {"people": [{"name": name, "label": label, "organization_label": organization} for name, label, organization in people]}
    )


def _stamps(records) -> dict[str, str | None]:
    return {name: group[0].organization_id for name, group in records.items()}


@pytest.mark.asyncio
async def test_each_person_is_stamped_with_the_organization_their_organization_label_names():
    run_prompt = AsyncMock(
        return_value=_picked(
            ("Rob Saka", "Council Member District 1", "City Council"), ("Katie Wilson", "Mayor", "Office of the Mayor")
        )
    )

    with patch(_RUN_PROMPT, new=run_prompt):
        extraction = await _collect([_COUNCIL, _MAYOR])

    assert extraction.heuristics_passed is True
    assert _stamps(extraction.records) == {"Rob Saka": "council", "Katie Wilson": "mayor"}


@pytest.mark.asyncio
async def test_the_prompt_offers_every_organization_but_the_default():
    default = KnownOrganization(id="officers", name="City Officers", meta_is_default=True)
    run_prompt = AsyncMock(return_value=_answer(("Rob Saka", "Council Member District 1")))

    with patch(_RUN_PROMPT, new=run_prompt):
        await _collect([_COUNCIL, _MAYOR, default])

    prompt = run_prompt.await_args.args[2]
    assert '- "City Council"' in prompt and '- "Office of the Mayor"' in prompt
    assert "City Officers" not in prompt


@pytest.mark.asyncio
async def test_when_both_attempts_fail_the_page_is_skipped():
    with patch(_RUN_PROMPT, new=AsyncMock(return_value=_answer(("Not On Page", "Mayor")))):
        extraction = await _collect([_COUNCIL, _MAYOR])

    assert extraction.heuristics_passed is False
    assert extraction.records == {}


@pytest.mark.asyncio
async def test_every_failed_attempt_leaves_its_reason_even_when_the_page_passes():
    """The first attempt invents someone, the retry does not. A name miss on any attempt is what
    marks the model as having made a person up."""
    run_prompt = AsyncMock(
        side_effect=[_answer(("Not On Page", "Mayor")), _answer(("Rob Saka", "Council Member District 1"))]
    )

    with patch(_RUN_PROMPT, new=run_prompt):
        extraction = await _collect([_COUNCIL, _MAYOR])

    assert extraction.heuristics_passed is True
    assert extraction.heuristics_failures == [HeuristicsFailure.NAME_NOT_IN_TEXT]


@pytest.mark.asyncio
async def test_a_page_that_passes_first_time_leaves_no_reasons():
    run_prompt = AsyncMock(return_value=_answer(("Rob Saka", "Council Member District 1")))

    with patch(_RUN_PROMPT, new=run_prompt):
        extraction = await _collect([_COUNCIL])

    assert extraction.heuristics_failures == []


@pytest.mark.asyncio
async def test_a_page_is_read_once_whatever_its_organizations():
    """The saving over one coverage question and one extraction per organization."""
    run_prompt = AsyncMock(return_value=_answer(("Rob Saka", "Council Member District 1")))

    with patch(_RUN_PROMPT, new=run_prompt):
        await _collect([_COUNCIL, _MAYOR])

    assert run_prompt.await_count == 1


@pytest.mark.asyncio
async def test_a_person_picked_into_no_organization_is_left_for_ingest_to_place():
    run_prompt = AsyncMock(return_value=_picked(("Rob Saka", "Council Member District 1", "none")))

    with patch(_RUN_PROMPT, new=run_prompt):
        extraction = await _collect([_COUNCIL, _MAYOR])

    assert _stamps(extraction.records) == {"Rob Saka": None}


@pytest.mark.asyncio
async def test_the_page_s_organizations_are_those_its_people_were_placed_into():
    """By the label they were listed under, else by their own label."""
    run_prompt = AsyncMock(
        return_value=_picked(
            ("Rob Saka", "Council Member District 1", "City Council"), ("Katie Wilson", "Mayor", "none")
        )
    )

    with patch(_RUN_PROMPT, new=run_prompt):
        extraction = await _collect([_COUNCIL, _MAYOR])

    assert extraction.organization_ids == ["council", "mayor"]


@pytest.mark.asyncio
async def test_a_failed_page_vouches_for_no_organization():
    run_prompt = AsyncMock(return_value=_picked(("Not On Page", "Mayor", "Office of the Mayor")))

    with patch(_RUN_PROMPT, new=run_prompt):
        extraction = await _collect([_COUNCIL, _MAYOR])

    assert extraction.heuristics_passed is False
    assert extraction.organization_ids == []


@pytest.mark.asyncio
async def test_an_email_the_page_does_not_show_is_dropped_without_a_retry():
    """The page spells it out in words, so the exact address is not in the text."""
    answer = PeopleArrayLLMResponseSchema(
        people=[ExtractedPersonRecord(name="Rob Saka", label="Council Member District 1", email="rsaka@seattle.gov")]
    )
    run_prompt = AsyncMock(return_value=answer)

    with patch(_RUN_PROMPT, new=run_prompt):
        extraction = await _collect([_COUNCIL])

    [(person, [record])] = extraction.records.items()
    assert (person, record.email) == ("Rob Saka", None)
    assert extraction.heuristics_failures == [HeuristicsFailure.EMAIL_NOT_IN_TEXT]
    assert run_prompt.await_count == 1
