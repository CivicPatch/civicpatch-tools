"""The budget gate the state scrape asks before claiming its next slice.

Thin, like the other activity tests: the arithmetic is `core.spend_limits`, unit-tested with no
mocks, and the two reads are integration-tested against real Postgres. What is worth pinning
here is the activity's contract — it asks the API over HTTP, like every other activity in this
file (see workers/pipeline_runs.py: this queue never opens its own database connection) — and it
answers *which* cap, where `None` means keep going.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.testing import ActivityEnvironment

from core.spend_limits import Cap
from routers.temporal.pipeline_run_activities import budget_cap_reached

pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, cap: str | None):
        self._cap = cap

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": {"cap": self._cap}}


def _patch(cap: str | None):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=_FakeResponse(cap))
    return patch(
        "routers.temporal.pipeline_run_activities.httpx.AsyncClient", return_value=client
    )


@pytest.mark.asyncio
async def test_a_state_under_both_caps_may_keep_spending():
    with _patch(None):
        assert await ActivityEnvironment().run(budget_cap_reached, "wa") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("cap", [Cap.STATE_MONTH, Cap.GLOBAL_MONTH])
async def test_the_cap_is_named_rather_than_reported_as_a_bare_stop(cap):
    """A caller told only "stop" cannot say whether to raise one state's cap or the global
    one, and the workflow logs this string when it halts a scrape."""
    with _patch(cap.value):
        assert await ActivityEnvironment().run(budget_cap_reached, "wa") == cap.value


@pytest.mark.asyncio
async def test_the_answer_is_a_plain_string_so_it_survives_temporal():
    """Activity results are serialised into workflow history. A StrEnum member round-trips as
    its value; returning the member itself would be relying on that rather than stating it."""
    with _patch(Cap.STATE_MONTH.value):
        result = await ActivityEnvironment().run(budget_cap_reached, "wa")

    assert type(result) is str
