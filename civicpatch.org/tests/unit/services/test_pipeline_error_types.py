"""The pipeline is a separate service naming an issue type across a wire."""

from unittest.mock import AsyncMock, patch

import pytest
from services.people_collector import _record_pipeline_error
from shared.utils.statuses import PipelineIssueType, PipelineRunErrorType

pytestmark = pytest.mark.unit

_RUN = "run-1"


def _context(**data):
    return {"data": data}


async def _file(**data):
    with patch(
        "services.people_collector.upsert_issue", new_callable=AsyncMock
    ) as upsert:
        await _record_pipeline_error(_RUN, _context(**data))
    return upsert.await_args.args


@pytest.mark.asyncio
async def test_a_recognised_error_type_is_filed_as_itself():
    run_id, issue_type, _ = await _file(error_step=PipelineRunErrorType.NO_ROSTER_FOUND)
    assert (run_id, issue_type) == (_RUN, PipelineRunErrorType.NO_ROSTER_FOUND)


@pytest.mark.asyncio
async def test_no_error_type_falls_back_to_pipeline_error():
    """The pipeline never sets `pipeline_error` itself; the server applies it."""
    _, issue_type, _ = await _file()
    assert issue_type == PipelineIssueType.PIPELINE_ERROR


@pytest.mark.asyncio
async def test_an_exception_message_does_not_become_an_issue_type():
    """`issue_type` is half of a UNIQUE constraint, so a raw message mints a new kind of issue
    per distinct string — `OPEN_ROUTER_TOKEN is not set` was one of them."""
    _, issue_type, detail = await _file(error_step="OPEN_ROUTER_TOKEN is not set")
    assert issue_type == PipelineIssueType.PIPELINE_ERROR
    assert detail == [{"reported_error_step": "OPEN_ROUTER_TOKEN is not set"}]


@pytest.mark.asyncio
async def test_the_original_detail_is_kept_alongside_the_rejected_type():
    _, _, detail = await _file(
        error_step="boom", error_detail={"error": "ValueError: boom"}
    )
    assert detail == [
        {"error": "ValueError: boom", "reported_error_step": "boom"}
    ]
