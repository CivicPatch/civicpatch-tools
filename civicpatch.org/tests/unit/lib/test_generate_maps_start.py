from unittest.mock import AsyncMock, patch

import pytest
from temporalio.common import WorkflowIDConflictPolicy

import lib.temporal.client as temporal_client
from lib.temporal.types import MAPS_TASK_QUEUE


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_second_start_for_the_same_state_fails_instead_of_building_twice():
    client = AsyncMock()
    with patch.object(temporal_client, "get_client", return_value=client):
        await temporal_client.start_generate_maps_workflow("or")

    started = client.start_workflow.call_args
    assert started.args == ("GenerateMapsWorkflow", "or")
    assert started.kwargs["id"] == "generate-maps-or"
    assert started.kwargs["task_queue"] == MAPS_TASK_QUEUE
    assert started.kwargs["id_conflict_policy"] == WorkflowIDConflictPolicy.FAIL
