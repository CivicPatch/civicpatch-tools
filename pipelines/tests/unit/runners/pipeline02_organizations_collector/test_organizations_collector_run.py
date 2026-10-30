"""A whole organizations_collector run through the engine, with cp.org and the model faked. What
is under test is the walk through its graph and what SELECT_SECTIONS hands EXTRACT."""

from datetime import datetime, timezone
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.engine import Machine, run_pipeline, terminal_states
from runners.pipeline02_organizations_collector.schemas import (
    OrganizationsCollectorConfig,
    OrganizationsCollectorContext,
    OrganizationsCollectorData,
    OrganizationsCollectorStep,
)
from runners.pipeline02_organizations_collector.transitions.graph import ORGANIZATIONS_COLLECTOR_TRANSITIONS
from runners.pipeline02_organizations_collector.transitions.main import TRANSITION_MAP
from shared.schemas import (
    FoundBy,
    GovernmentForm,
    GoverningLaw,
    GoverningLawKind,
    GoverningLawOrganizations,
    GoverningLawOrganizationsExtras,
    GoverningLawPost,
    QuoteScope,
    Source,
    SourceExtras,
)
from shared.utils.government_forms import DerivedOrganization
from shared.utils.layered_config import (
    Classification,
    ConfigFile,
    ConfigRole,
    GovernedBy,
    GoverningLawConfig,
    GovernmentFormConfig,
    merged_config,
)
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES, PipelineRunStatus

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_CHAPTERS = "https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX"
# The fake pages' urls are `_CHAPTERS/<page id>`, so the page "statute" is the town's general law.
_VERMONT = GoverningLawConfig(
    charter_terms=["charter"],
    classifications={"town": Classification(governed_by=GovernedBy.CHARTER_OR_GENERAL_LAW, general_law=[f"{_CHAPTERS}/statute"])},
)
_CONFIG = merged_config(
    ConfigFile(roles=[ConfigRole(id="member", label="Member", aliases=["Select Board Member"])]),
    ConfigFile(
        government_forms={
            GovernmentForm.OPEN_TOWN_MEETING: GovernmentFormConfig(
                organizations=[DerivedOrganization(name="Select Board", role_labels=["Select Board Member"])]
            )
        }
    ),
    ConfigFile(governing_law=_VERMONT),
)
_STATUTE = "- **§ 871. Officers**\nThe town officers shall be elected at the annual meeting.\n"


def _governing_law(source_page_ids: list[str], kind: GoverningLawKind = GoverningLawKind.CHARTER) -> GoverningLaw:
    return GoverningLaw(
        kind=kind if source_page_ids else GoverningLawKind.NONE_FOUND,
        classification="town",
        found_by=FoundBy.STATE_INDEX,
        source_page_ids=source_page_ids,
        collected_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
        cost_usd=None,
    )


def _context(governing_law: GoverningLaw | None) -> OrganizationsCollectorContext:
    return OrganizationsCollectorContext(
        pipeline_run_id="run-1",
        current_state=PipelineRunStatus.INIT,
        data=OrganizationsCollectorData(
            jurisdiction_ocdid=_OCDID,
            config=OrganizationsCollectorConfig(
                name="Stowe town",
                governing_law=governing_law,
                jurisdiction_config=_CONFIG,
                government_form=GovernmentForm.OPEN_TOWN_MEETING,
            ),
        ),
    )


MAIN = "runners.pipeline02_organizations_collector.transitions.main"
_SHORT_CHARTER = "- **§ 1. Selectboard**\nThe Selectboard shall consist of five members elected at large.\n"
_LONG_CHARTER = (
    "- **§ 1. Corporate existence**\n" + "The town continues. " * 6_000 + "\n"
    "- **§ 2. Selectboard; election**\nThe Selectboard shall consist of five members elected at large.\n"
    "- **§ 3. Water department**\nThe water department supplies water.\n"
)


class _Run(NamedTuple):
    states: list[str]
    context: OrganizationsCollectorContext
    pick: AsyncMock
    api: MagicMock


async def _walk(
    context: OrganizationsCollectorContext,
    pages: dict[str, str] | None = None,
    picked: list[str] | None = None,
    stored: GoverningLawOrganizations | None = None,
) -> _Run:
    """`pages` maps a source page id to its cached text; `picked` is the model's heading pick;
    `stored` is an answer cp.org holds for the run's input hash."""
    pages = pages or {}
    engine_api = MagicMock()
    engine_api.fetch_pipeline_run_status = AsyncMock(return_value=PipelineRunStatus.RUNNING)
    engine_api.update_pipeline_run_status = AsyncMock()
    api = MagicMock()
    api.get_governing_law_source_page = AsyncMock(
        side_effect=lambda _client, _logger, _ocdid, page_id: {"id": page_id, "source_url": f"{_CHAPTERS}/{page_id}", "text": pages[page_id]}
    )
    api.get_extras_organizations_by_input_hash = AsyncMock(return_value=stored)
    api.patch_jurisdiction_extras = AsyncMock()
    pick = AsyncMock(return_value={"sections": picked or []})
    seen: list[OrganizationsCollectorContext] = []

    async def capture(_limits, _logger, extracted, _client):
        seen.append(extracted)
        return extracted, OrganizationsCollectorStep.VERIFY

    handlers = {**TRANSITION_MAP, OrganizationsCollectorStep.EXTRACT: capture}
    with patch("runners.engine.civicpatch_api", engine_api), patch("runners.engine.log_system_usage"), patch(
        f"{MAIN}.civicpatch_api", api
    ), patch(f"{MAIN}.open_router_llm.run_prompt", new=pick):
        walked = await run_pipeline(context, MagicMock(), Machine(transitions=ORGANIZATIONS_COLLECTOR_TRANSITIONS, handlers=handlers), MagicMock())
    states = [call.kwargs["status"] for call in engine_api.update_pipeline_run_status.call_args_list]
    return _Run(states=states, context=seen[0] if seen else walked, pick=pick, api=api)


def test_every_state_the_engine_handles_is_in_the_graph_and_vice_versa():
    before_the_engine = {PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING}
    engine_states = {
        state for state, allowed in ORGANIZATIONS_COLLECTOR_TRANSITIONS.items() if allowed and state not in before_the_engine
    }

    assert set(TRANSITION_MAP) == engine_states


def test_the_graph_ends_where_every_run_ends():
    assert set(terminal_states(ORGANIZATIONS_COLLECTOR_TRANSITIONS)) == set(TERMINAL_PIPELINE_RUN_STATUSES)


@pytest.mark.asyncio
async def test_a_jurisdiction_with_cached_law_is_read_then_written():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _SHORT_CHARTER})

    assert run.states == ["INIT", "SELECT_SECTIONS", "EXTRACT", "VERIFY", "WRITE", "SUCCESS"]


@pytest.mark.asyncio
async def test_a_jurisdiction_with_no_cached_law_goes_straight_to_write():
    assert (await _walk(_context(_governing_law([])))).states == ["INIT", "SELECT_SECTIONS", "WRITE", "SUCCESS"]


@pytest.mark.asyncio
async def test_a_jurisdiction_plan_1_has_not_reached_goes_straight_to_write():
    assert (await _walk(_context(None))).states == ["INIT", "SELECT_SECTIONS", "WRITE", "SUCCESS"]


@pytest.mark.asyncio
async def test_a_charter_that_fits_is_read_whole_without_a_pick():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _SHORT_CHARTER})

    assert run.context.data.selected_governing_law_text == "# Charter\n\n" + _SHORT_CHARTER
    run.pick.assert_not_called()


@pytest.mark.asyncio
async def test_the_charter_is_read_first_and_the_general_law_after_it():
    run = await _walk(_context(_governing_law(["statute", "charter"])), {"charter": _SHORT_CHARTER, "statute": _STATUTE})

    assert run.context.data.selected_governing_law_text == f"# Charter\n\n{_SHORT_CHARTER}\n\n# General law\n\n{_STATUTE}"


@pytest.mark.asyncio
async def test_a_general_law_jurisdictions_pages_are_all_general_law():
    run = await _walk(
        _context(_governing_law(["page-1"], kind=GoverningLawKind.GENERAL_LAW)), {"page-1": _SHORT_CHARTER}
    )

    assert run.context.data.selected_governing_law_text == "# General law\n\n" + _SHORT_CHARTER


@pytest.mark.asyncio
async def test_a_long_charter_is_read_as_the_sections_the_model_picks():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _LONG_CHARTER}, picked=["H0002"])

    assert run.context.data.selected_governing_law_text == "# Charter\n\n- **§ 2. Selectboard; election**\nThe Selectboard shall consist of five members elected at large."


@pytest.mark.asyncio
async def test_a_pick_naming_nothing_falls_back_to_the_headings_that_name_the_government():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _LONG_CHARTER}, picked=[])

    assert run.context.data.selected_governing_law_text == "# Charter\n\n- **§ 2. Selectboard; election**\nThe Selectboard shall consist of five members elected at large."


def _stored_answer() -> GoverningLawOrganizations:
    """Another town's answer from the same page: it cites that town's row for the page."""
    member = GoverningLawPost(
        role="member", label="Selectboard member", organization_id="Select Board", maximum_memberships=5,
        sources=[Source(url=f"{_CHAPTERS}/page-1", note="five members", extras=SourceExtras(source_page_id="other-town-row", matched_in=QuoteScope.SENTENCE))],
    )
    return GoverningLawOrganizations(
        posts=[member], extras=GoverningLawOrganizationsExtras(governing_law_collected_at=datetime(2026, 10, 1, tzinfo=timezone.utc), input_hash="7c21")
    )


@pytest.mark.asyncio
async def test_an_answer_read_from_the_same_inputs_is_copied_without_asking_the_model():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _LONG_CHARTER}, stored=_stored_answer())

    assert run.states == ["INIT", "SELECT_SECTIONS", "WRITE", "SUCCESS"]
    run.pick.assert_not_called()
    [call] = run.api.patch_jurisdiction_extras.await_args_list
    written = call.args[2].extras_organizations
    assert [post.label for post in written.posts] == ["Selectboard member"]
    assert written.posts[0].sources[0].extras.source_page_id == "page-1"
    assert written.extras.governing_law_collected_at == datetime(2026, 10, 19, tzinfo=timezone.utc)
    assert written.extras.input_hash == run.api.get_extras_organizations_by_input_hash.await_args.args[3]


@pytest.mark.asyncio
async def test_with_nothing_to_copy_the_law_is_read_and_the_hash_kept_for_write():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _SHORT_CHARTER})

    [call] = run.api.get_extras_organizations_by_input_hash.await_args_list
    assert run.context.data.input_hash == call.args[3]
    assert run.context.data.pending_asks


@pytest.mark.asyncio
async def test_select_sections_queues_a_question_for_each_role():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _SHORT_CHARTER})

    assert [(ask.organization_name, ask.role_id) for ask in run.context.data.pending_asks] == [("Select Board", "member")]
