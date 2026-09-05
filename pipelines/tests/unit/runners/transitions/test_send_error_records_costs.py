from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runners.people_collector.transitions.main import send_error_transition

pytestmark = pytest.mark.unit

_RUN = "run-1"
_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"


def _context():
    context = MagicMock()
    context.pipeline_run_id = _RUN
    context.data.jurisdiction_ocdid = _OCDID
    return context


def _patches(log_costs, send_error):
    return (
        patch("runners.people_collector.transitions.main.cost_utils.log_costs", log_costs),
        patch("runners.people_collector.transitions.main.send_error", send_error),
    )


@pytest.mark.asyncio
async def test_a_failed_run_writes_what_it_spent():
    """It burned tokens before it failed. 24 of 49 dismissed scrapes on dev recorded nothing."""
    log_costs, send_error = MagicMock(), AsyncMock()
    p1, p2 = _patches(log_costs, send_error)
    with p1, p2:
        await send_error_transition(MagicMock(), MagicMock(), _context(), MagicMock())

    log_costs.assert_called_once_with(_RUN, _OCDID)


@pytest.mark.asyncio
async def test_costs_are_written_before_the_artifacts_are_zipped():
    """`send_error` zips the directory, so a later write would miss the archive."""
    order = []
    log_costs = MagicMock(side_effect=lambda *_: order.append("costs"))
    send_error = AsyncMock(side_effect=lambda *_: order.append("send"))
    p1, p2 = _patches(log_costs, send_error)
    with p1, p2:
        await send_error_transition(MagicMock(), MagicMock(), _context(), MagicMock())

    assert order == ["costs", "send"]


@pytest.mark.asyncio
async def test_an_unwritable_cost_file_does_not_cost_us_the_error_report():
    log_costs = MagicMock(side_effect=OSError("read-only"))
    send_error = AsyncMock()
    p1, p2 = _patches(log_costs, send_error)
    with p1, p2:
        await send_error_transition(MagicMock(), MagicMock(), _context(), MagicMock())

    send_error.assert_awaited_once()
