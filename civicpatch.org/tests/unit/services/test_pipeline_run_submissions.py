"""A collector run's upload: its costs recorded, its issue filed, its temp dir removed. The database
is patched at the service boundary; the zip is real."""

import json
import os
import tempfile
import zipfile
from unittest.mock import AsyncMock, patch

import pytest
from shared.utils.statuses import PipelineIssueType, PipelineRunKind

from services.pipeline_run_submissions import COSTS_FILE, CONTEXT_FILE, handle_pipeline_run_submission

pytestmark = pytest.mark.unit

MODULE = "services.pipeline_run_submissions"
_RUN_ID = "run-1"
_CALL = {"prompt_name": "p2_role", "gateway": "openrouter", "model": "deepseek/deepseek-v4-flash", "input_tokens": 10, "output_tokens": 5}


def _upload(context_data: dict) -> tuple[str, str]:
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "run.zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        zipf.writestr(CONTEXT_FILE, json.dumps({"pipeline_run_id": _RUN_ID, "data": context_data}))
        zipf.writestr(COSTS_FILE, json.dumps({"llm_costs": [_CALL]}))
    return zip_path, temp_dir


@pytest.mark.asyncio
async def test_a_collector_upload_records_its_costs_files_its_issue_and_leaves_no_temp_dir():
    zip_path, temp_dir = _upload({"input_hash": None})

    with patch(f"{MODULE}.record_calls", new=AsyncMock(return_value=1)) as record, patch(f"{MODULE}.upsert_issue", new=AsyncMock()) as upsert:
        await handle_pipeline_run_submission(PipelineRunKind.ORGANIZATIONS_COLLECTOR, _RUN_ID, zip_path, temp_dir)

    record.assert_awaited_once_with(_RUN_ID, [_CALL])
    upsert.assert_awaited_once_with(_RUN_ID, PipelineIssueType.NO_GOVERNING_LAW, [{}])
    assert not os.path.exists(temp_dir)


@pytest.mark.asyncio
async def test_a_run_with_no_issue_records_its_costs_and_files_nothing():
    zip_path, temp_dir = _upload({"input_hash": "7c21", "stopped_at_cost_cap": False})

    with patch(f"{MODULE}.record_calls", new=AsyncMock(return_value=1)) as record, patch(f"{MODULE}.upsert_issue", new=AsyncMock()) as upsert:
        await handle_pipeline_run_submission(PipelineRunKind.ORGANIZATIONS_COLLECTOR, _RUN_ID, zip_path, temp_dir)

    record.assert_awaited_once()
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_unreadable_upload_is_logged_and_its_temp_dir_still_removed():
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "run.zip")
    with open(zip_path, "w") as broken:
        broken.write("not a zip")

    with patch(f"{MODULE}.record_calls", new=AsyncMock()) as record:
        await handle_pipeline_run_submission(PipelineRunKind.GOVERNING_LAW_COLLECTOR, _RUN_ID, zip_path, temp_dir)

    record.assert_not_awaited()
    assert not os.path.exists(temp_dir)
