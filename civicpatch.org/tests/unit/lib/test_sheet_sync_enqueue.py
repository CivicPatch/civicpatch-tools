"""How a sheet sync is asked for — the workflow id and the start semantics.

Nothing here runs a workflow. What is asserted is the two decisions that make coalescing safe,
because both are invisible at runtime until data goes missing:

  * the id is the *state*, so every publish in one state collapses into one tab rewrite;
  * the start carries a **signal**, not `USE_EXISTING`, so a request arriving mid-activity
    earns another pass instead of being dropped.

Swapping the second for `id_conflict_policy=USE_EXISTING` would look tidier, pass every other
test, and silently lose the last publish of every batch.
"""

from unittest.mock import AsyncMock, patch

import pytest

import lib.temporal.client as temporal_client


def _client() -> AsyncMock:
    client = AsyncMock()
    client.start_workflow = AsyncMock()
    return client


def _started(client: AsyncMock) -> dict:
    return client.start_workflow.call_args.kwargs


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_roster_sync_is_keyed_on_the_state():
    """One tab per state is the conflict domain, so forty MA towns publishing must not become
    forty rewrites of the MA tab."""
    client = _client()
    with patch.object(temporal_client, "_get_client", return_value=client):
        await temporal_client.enqueue_roster_sheet_sync("ma")

    assert _started(client)["id"] == "roster-sheet-sync:ma"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_roster_sync_signals_rather_than_dropping_a_duplicate():
    """The lost-update guard. `USE_EXISTING` drops a request that lands while the workflow is
    running, which between the activity's database read and the workflow closing means the
    change never reaches the sheet — and only the next publish in that state would repair it."""
    client = _client()
    with patch.object(temporal_client, "_get_client", return_value=client):
        await temporal_client.enqueue_roster_sheet_sync("tx")

    started = _started(client)
    assert started["start_signal"] == "mark_dirty"
    assert "id_conflict_policy" not in started


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_jurisdiction_sync_is_a_singleton():
    """That tab covers every state, so a second request while one runs is the same work — the
    one place where dropping a duplicate is right."""
    client = _client()
    with patch.object(temporal_client, "_get_client", return_value=client):
        await temporal_client.enqueue_jurisdictions_sheet_sync()

    started = _started(client)
    assert started["id"] == "jurisdictions-sheet-sync"
    assert started["id_conflict_policy"] is not None
    assert "start_signal" not in started
