"""A whole organizations_collector run through the engine, with cp.org and the model faked. What
is under test is the walk through its graph and what SELECT_SECTIONS hands EXTRACT."""

from datetime import datetime, timezone
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.engine import Machine, run_pipeline, terminal_states
from runners.organizations_collector.schemas import (
    OrganizationsCollectorConfig,
    OrganizationsCollectorContext,
    OrganizationsCollectorData,
    OrganizationsCollectorStep,
)
from runners.organizations_collector.transitions.graph import ORGANIZATIONS_COLLECTOR_TRANSITIONS
from runners.organizations_collector.transitions.main import TRANSITION_MAP
from shared.schemas import FoundBy, GovernmentForm, GoverningLaw, GoverningLawKind
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


MAIN = "runners.organizations_collector.transitions.main"
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


async def _walk(context: OrganizationsCollectorContext, pages: dict[str, str] | None = None, picked: list[str] | None = None) -> _Run:
    """`pages` maps a source page id to its cached text; `picked` is the model's heading pick."""
    pages = pages or {}
    engine_api = MagicMock()
    engine_api.fetch_pipeline_run_status = AsyncMock(return_value=PipelineRunStatus.RUNNING)
    engine_api.update_pipeline_run_status = AsyncMock()
    api = MagicMock()
    api.get_governing_law_source_page = AsyncMock(
        side_effect=lambda _client, _ocdid, page_id: {"id": page_id, "source_url": f"{_CHAPTERS}/{page_id}", "text": pages[page_id]}
    )
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
    return _Run(states=states, context=seen[0] if seen else walked, pick=pick)


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


@pytest.mark.asyncio
async def test_select_sections_queues_a_question_for_each_role():
    run = await _walk(_context(_governing_law(["page-1"])), {"page-1": _SHORT_CHARTER})

    assert [(ask.organization_name, ask.role_id) for ask in run.context.data.pending_asks] == [("Select Board", "member")]
