"""One extraction per organization, stamped with its id; unscoped unless there are organizations to tell apart."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runners.people_collector.schemas import (
    ExtractedPersonRecord,
    Link,
    LinkStatus,
    OrganizationCoverageResponseSchema,
    PeopleArrayLLMResponseSchema,
    ProcessPageContentStep,
)
from runners.people_collector.steps.step_04_process_page_content.extraction_scopes import (
    extraction_scopes,
)
from runners.people_collector.steps.step_04_process_page_content.process_page_content import (
    collect_page_records,
)
from shared.schemas import KnownOrganization, Post
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_PAGE = Link(url="https://seattle.gov/elected-officials", status=LinkStatus.PREPROCESSED.value)
_CONTENT = "Elected officials: Mayor Katie Wilson. Council Member District 1: Rob Saka."
_RUN_PROMPT = (
    "runners.people_collector.steps.step_04_process_page_content.process_page_content"
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


# The first line of `page_covers_organization_prompt`, which is asked once per body before any
# extraction runs.
_COVERAGE_PROMPT = "Decide whether the provided page content carries people"


def _by_organization(
    council: PeopleArrayLLMResponseSchema,
    mayor: PeopleArrayLLMResponseSchema,
    covers: tuple[bool, bool] = (True, True),
):
    """A fake LLM that answers according to which organization the prompt names.

    Coverage is asked first, one call per body; these tests are about what happens after, so it
    answers yes for both unless a test says otherwise.
    """
    covers_council, covers_mayor = covers

    async def run_prompt(_run_id, _ocdid, prompt, **_kwargs):
        if _COVERAGE_PROMPT in prompt:
            is_council = "Body: City Council" in prompt
            return OrganizationCoverageResponseSchema(
                covers=covers_council if is_council else covers_mayor
            )
        return council if "hold a post in City Council" in prompt else mayor

    return run_prompt


async def _collect(organizations: list[KnownOrganization]):
    return await collect_page_records(
        pipeline_run_context_factory(steps={}),
        _PAGE,
        _CONTENT,
        [],
        organizations,
        ProcessPageContentStep(records={}),
        {},
        MagicMock(),
    )


def _stamps(records) -> dict[str, str | None]:
    return {name: group[0].organization_id for name, group in records.items()}


def test_no_organizations_is_one_unscoped_run():
    [scope] = extraction_scopes([])

    assert scope.organization_id is None
    assert scope.prompt_organization is None


def test_one_organization_runs_unscoped_but_is_stamped_with_its_id():
    [scope] = extraction_scopes([_COUNCIL])

    assert scope.organization_id == "council"
    assert scope.prompt_organization is None


def test_several_organizations_each_get_a_scoped_run_with_their_post_labels():
    scopes = extraction_scopes([_COUNCIL, _MAYOR])

    assert [(s.organization_id, s.prompt_organization.name, s.prompt_organization.posts) for s in scopes if s.prompt_organization] == [
        ("council", "City Council", ["Council Member District 1"]),
        ("mayor", "Office of the Mayor", ["Mayor"]),
    ]


@pytest.mark.asyncio
async def test_each_organizations_records_are_stamped_with_that_organization():
    fake = _by_organization(_answer(("Rob Saka", "Council Member District 1")), _answer(("Katie Wilson", "Mayor")))

    with patch(_RUN_PROMPT, new=AsyncMock(side_effect=fake)):
        records, passed = await _collect([_COUNCIL, _MAYOR])

    assert passed is True
    assert _stamps(records) == {"Rob Saka": "council", "Katie Wilson": "mayor"}


@pytest.mark.asyncio
async def test_an_organization_failing_the_heuristics_twice_does_not_discard_the_others():
    """A name that is not on the page fails the heuristics; that organization's retry fails too."""
    fake = _by_organization(_answer(("Rob Saka", "Council Member District 1")), _answer(("Not On Page", "Mayor")))

    with patch(_RUN_PROMPT, new=AsyncMock(side_effect=fake)) as run_prompt:
        records, passed = await _collect([_COUNCIL, _MAYOR])

    assert passed is True
    assert _stamps(records) == {"Rob Saka": "council"}
    # Two coverage questions, then council once and mayor twice.
    assert run_prompt.await_count == 5


@pytest.mark.asyncio
async def test_a_single_organization_sends_the_unscoped_prompt():
    run_prompt = AsyncMock(return_value=_answer(("Rob Saka", "Council Member District 1")))

    with patch(_RUN_PROMPT, new=run_prompt):
        records, _ = await _collect([_COUNCIL])

    assert "TARGET BODY" not in run_prompt.await_args.args[2]
    assert _stamps(records) == {"Rob Saka": "council"}


@pytest.mark.asyncio
async def test_when_every_organization_fails_the_page_is_skipped():
    fake = _by_organization(_answer(("Not On Page", "Mayor")), _answer(("Not On Page", "Mayor")))

    with patch(_RUN_PROMPT, new=AsyncMock(side_effect=fake)):
        records, passed = await _collect([_COUNCIL, _MAYOR])

    assert passed is False
    assert records == {}


@pytest.mark.asyncio
async def test_a_body_the_page_does_not_cover_is_not_extracted_for():
    """The saving: a council roster gets one extraction, not one per body in the jurisdiction."""
    fake = _by_organization(
        _answer(("Rob Saka", "Council Member District 1")),
        _answer(("Katie Wilson", "Mayor")),
        covers=(True, False),
    )

    with patch(_RUN_PROMPT, new=AsyncMock(side_effect=fake)) as run_prompt:
        records, passed = await _collect([_COUNCIL, _MAYOR])

    assert passed is True
    assert _stamps(records) == {"Rob Saka": "council"}
    # Two coverage questions, then only the council's extraction.
    assert run_prompt.await_count == 3


@pytest.mark.asyncio
async def test_a_page_covering_no_known_body_still_runs_them_all():
    """An empty answer is not evidence the page is empty — it may carry a body nobody holds yet,
    and withholding every extraction would drop those people on the floor."""
    fake = _by_organization(
        _answer(("Rob Saka", "Council Member District 1")),
        _answer(("Katie Wilson", "Mayor")),
        covers=(False, False),
    )

    with patch(_RUN_PROMPT, new=AsyncMock(side_effect=fake)):
        records, passed = await _collect([_COUNCIL, _MAYOR])

    assert passed is True
    assert _stamps(records) == {"Rob Saka": "council", "Katie Wilson": "mayor"}
