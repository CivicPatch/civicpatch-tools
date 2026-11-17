"""The status report the workflow makes when it fails a run itself.

Thin, like the other activity tests: what it pins is the contract — the failure travels on the
same PATCH that settles the run, because a run killed mid-scrape uploads no report and its issue
has to come from somewhere. Whether the API then files it is `services/pipeline_runs`, unit-tested
beside this.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.testing import ActivityEnvironment

from routers.temporal.pipeline_run_activities import update_pipeline_run_status

pytestmark = pytest.mark.unit

RUN_ID = "11111111-2222-3333-4444-555555555555"


class _Accepted:
    def raise_for_status(self):
        pass


def _patch_client():
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.patch = AsyncMock(return_value=_Accepted())
    return client, patch(
        "routers.temporal.pipeline_run_activities.httpx.AsyncClient", return_value=client
    )


@pytest.mark.asyncio
async def test_a_failure_rides_on_the_status_report():
    client, patched = _patch_client()
    with patched:
        await ActivityEnvironment().run(
            update_pipeline_run_status,
            RUN_ID,
            "ERROR",
            None,
            "pipeline_error",
            {"error": "Pipeline run reported nothing new for 0:30:00"},
        )

    assert client.patch.await_args.kwargs["json"] == {
        "status": "ERROR",
        "progress": None,
        "error_type": "pipeline_error",
        "error_detail": {"error": "Pipeline run reported nothing new for 0:30:00"},
    }


@pytest.mark.asyncio
async def test_a_report_with_no_failure_sends_no_issue_fields():
    """The ordinary path: the pipeline reports its progress and files its own issues."""
    client, patched = _patch_client()
    with patched:
        await ActivityEnvironment().run(update_pipeline_run_status, RUN_ID, "RUNNING", 40)

    assert client.patch.await_args.kwargs["json"] == {"status": "RUNNING", "progress": 40}
