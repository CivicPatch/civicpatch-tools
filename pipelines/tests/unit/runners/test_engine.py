"""The engine loop: which states it may move between, and how it leaves.

`PIPELINE_RUN_TRANSITIONS` is the graph. The engine checks every step's answer against it,
so a handler that returns an impossible state fails here rather than writing that state outward.

`civicpatch_api` is patched because it is HTTP — a real process boundary. Transition maps are
stubs: what is under test is the loop, not any step.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.engine import IllegalTransition, run_pipeline
from runners.people_collector.schemas import PipelineStatus
from shared.utils.statuses import PipelineRunStatus
from tests.factories.pipeline_run_context import pipeline_run_context_factory


def _reported_statuses(update_mock) -> list[str]:
    return [call.kwargs["status"] for call in update_mock.call_args_list]


def _at(state: PipelineStatus):
    return pipeline_run_context_factory({}).copy(update={"current_state": state})


def _returning(next_state: PipelineStatus):
    async def _fn(_limits, _logger, context, _api_client):
        return context, next_state

    return _fn


def _patched_api(reported_status=PipelineRunStatus.RUNNING):
    api = patch("runners.engine.civicpatch_api")
    mock = api.start()
    mock.fetch_pipeline_run_status = AsyncMock(return_value=reported_status)
    mock.update_pipeline_run_status = AsyncMock()
    return api, mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_cancelled_run_reports_cancelled_not_the_step_it_was_on():
    """Cancelling used to leave via `return`, which still ran the `finally` reporting
    `current_state` — so a cancelled run's last word was `SCRAPE_PAGE`."""
    should_not_run = AsyncMock()
    api, mock = _patched_api(PipelineRunStatus.CANCELLED)
    try:
        with patch("runners.engine.log_system_usage"):
            result = await run_pipeline(
                _at(PipelineStatus.SCRAPE_PAGE),
                MagicMock(),
                {PipelineStatus.SCRAPE_PAGE: should_not_run},
                AsyncMock(),
            )
    finally:
        api.stop()

    assert _reported_statuses(mock.update_pipeline_run_status)[-1] == (
        PipelineStatus.CANCELLED.value
    )
    assert result.current_state == PipelineStatus.CANCELLED
    # Cancelling stops work; it does not run one more step first.
    should_not_run.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_step_naming_a_state_the_graph_forbids_raises():
    """SAVE_OUTPUT leads only to SEND_SUCCESS. A step answering otherwise is a bug, and must not
    reach `update_pipeline_run_status` — the whole point of keeping the graph in code."""
    api, mock = _patched_api()
    try:
        with patch("runners.engine.log_system_usage"):
            with pytest.raises(IllegalTransition) as raised:
                await run_pipeline(
                    _at(PipelineStatus.SAVE_OUTPUT),
                    MagicMock(),
                    {PipelineStatus.SAVE_OUTPUT: _returning(PipelineStatus.CLEANUP)},
                    AsyncMock(),
                )
    finally:
        api.stop()

    assert raised.value.current == PipelineStatus.SAVE_OUTPUT
    assert raised.value.requested == PipelineStatus.CLEANUP
    assert PipelineStatus.CLEANUP.value not in _reported_statuses(
        mock.update_pipeline_run_status
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_run_walks_the_graph_to_a_terminal_state():
    """The other half: legal edges pass, and the loop stops at a state nothing follows."""
    api, _ = _patched_api()
    try:
        with patch("runners.engine.log_system_usage"):
            result = await run_pipeline(
                _at(PipelineStatus.SAVE_OUTPUT),
                MagicMock(),
                {
                    PipelineStatus.SAVE_OUTPUT: _returning(PipelineStatus.SEND_SUCCESS),
                    PipelineStatus.SEND_SUCCESS: _returning(PipelineStatus.SUCCESS),
                },
                AsyncMock(),
            )
    finally:
        api.stop()

    assert result.current_state == PipelineStatus.SUCCESS


@pytest.mark.unit
def test_every_state_the_engine_handles_is_in_the_graph_and_vice_versa():
    """`TRANSITION_MAP` says who runs a state; `PIPELINE_RUN_TRANSITIONS` says where it may go.
    Adding one without the other is the drift this pins — a handler with no declared edges
    raises on its first transition, and an edge with no handler is a KeyError mid-run."""
    from runners.people_collector.transitions.main import TRANSITION_MAP
    from shared.utils.statuses import PIPELINE_RUN_TRANSITIONS

    # PENDING and RUNNING are civicpatch.org's; the engine starts at INIT.
    before_the_engine = {PipelineStatus.PENDING, PipelineStatus.RUNNING}
    engine_states = {
        state
        for state, allowed in PIPELINE_RUN_TRANSITIONS.items()
        if allowed and state not in before_the_engine
    }

    assert set(TRANSITION_MAP) == engine_states
