from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from temporalio.common import WorkflowIDConflictPolicy

import lib.temporal.client as temporal_client
from lib.temporal.types import SINKS_TASK_QUEUE, OpenDataBatchCommitRequest, OpenDataCommitItem


def _batch(changeset_ids: list[str]) -> OpenDataBatchCommitRequest:
    item = OpenDataCommitItem(
        file_path="data/wa/seattle.yml",
        changeset_ids=changeset_ids,
        jurisdiction_ocdid="ocd-division/country:us/state:wa/place:seattle",
    )
    return OpenDataBatchCommitRequest(batch_id="batch-1", items=[item], commit_message="Publish")


async def _start(request: OpenDataBatchCommitRequest) -> dict[str, Any]:
    client = AsyncMock()
    with patch.object(temporal_client, "get_client", return_value=client):
        await temporal_client.enqueue_write_open_data_batch(request)
    return client.start_workflow.call_args.kwargs


@pytest.mark.unit
@pytest.mark.asyncio
async def test_an_open_data_batch_is_keyed_on_the_batch_and_its_selection():
    started = await _start(_batch(["c2", "c1"]))
    reordered = await _start(_batch(["c1", "c2"]))
    more = await _start(_batch(["c1", "c2", "c3"]))

    assert started["id"].startswith("sink:open-data:batch:batch-1:")
    assert started["id"] == reordered["id"]
    assert started["id"] != more["id"]
    assert started["task_queue"] == SINKS_TASK_QUEUE
    assert started["id_conflict_policy"] == WorkflowIDConflictPolicy.USE_EXISTING
