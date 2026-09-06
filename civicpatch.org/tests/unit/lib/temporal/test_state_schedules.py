"""Declaring one schedule per state from `state_settings`.

The Temporal client is mocked because it is a real process boundary. What is asserted is the
declaration itself: which states get a schedule, what the retire pass is told about them, and
that a manual state is removed rather than left firing.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.scrape_schedule import schedule_id
from lib.temporal import schedules
from schemas.state_settings import StateSettings

pytestmark = pytest.mark.unit


def _client():
    client = MagicMock()
    client.create_schedule = AsyncMock()
    handle = MagicMock()
    handle.update = AsyncMock()
    handle.delete = AsyncMock()
    handle.trigger = AsyncMock()
    client.get_schedule_handle = MagicMock(return_value=handle)
    return client, handle


def _settings(**states):
    return patch.object(
        schedules, "get_all_state_settings", new=AsyncMock(return_value=states)
    )


@pytest.mark.asyncio
async def test_only_states_with_a_cadence_get_a_schedule():
    """NULL cadence is what `manual` means: no schedule, and the state's candidates never
    drain on their own."""
    client, _handle = _client()
    with _settings(
        wa=StateSettings(state="wa", cadence_days=30),
        tn=StateSettings(state="tn"),  # manual
    ):
        declared = await schedules._register_state_schedules(client)

    assert declared == {schedule_id("wa")}


@pytest.mark.asyncio
async def test_the_declared_ids_reach_the_retire_pass():
    """The trap this plan flagged before it was built: `_retire_undeclared_schedules` deletes
    anything not declared, so state schedules missing from that set would all be deleted on the
    next worker start."""
    client, _handle = _client()
    retired = AsyncMock()
    with _settings(wa=StateSettings(state="wa", cadence_days=30)), patch.object(
        schedules, "_retire_undeclared_schedules", new=retired
    ), patch.object(schedules, "_ensure_schedule", new=AsyncMock(return_value=False)):
        await schedules.register_schedules(client)

    declared = retired.await_args.args[1]
    assert schedule_id("wa") in declared
    assert "od-sync" in declared  # and the fixed five are still there


@pytest.mark.asyncio
async def test_a_state_switched_back_to_manual_has_its_schedule_deleted():
    """Not merely undeclared — this path has no retire pass behind it, so the delete is
    explicit. A `manual` state that kept firing is the worst failure this feature has."""
    client, handle = _client()
    with patch.object(
        schedules,
        "get_state_settings",
        new=AsyncMock(return_value=StateSettings(state="wa")),
    ):
        await schedules.reconcile_state_schedule(client, "wa")

    handle.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_writing_a_cadence_converges_that_state_and_nothing_else():
    """Targeted: `register_schedules` ends in a namespace-wide retire, and running that from an
    API request would let one write delete schedules it knows nothing about."""
    client, _handle = _client()
    ensure = AsyncMock(return_value=False)
    with patch.object(
        schedules,
        "get_state_settings",
        new=AsyncMock(
            return_value=StateSettings(
                state="wa", cadence_days=7, cadence_anchor=date(2026, 9, 1)
            )
        ),
    ), patch.object(schedules, "_ensure_schedule", new=ensure):
        await schedules.reconcile_state_schedule(client, "wa")

    assert ensure.await_args.args[1] == schedule_id("wa")
    spec = ensure.await_args.args[2].spec
    assert spec.intervals[0].every == timedelta(days=7)
