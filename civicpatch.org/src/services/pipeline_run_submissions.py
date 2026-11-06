"""What a collector run sends when it ends: its context and its model calls, in one zip. The calls are
recorded and the run's issue filed, by `core.pipeline_run_issues`."""

import json
import logging
import shutil
import zipfile

from core.pipeline_run_issues import ISSUE_READERS
from database.issues import upsert_issue
from database.llm_calls import record_calls
from shared.utils.statuses import PipelineRunKind

logger = logging.getLogger(__name__)

CONTEXT_FILE = "context.json"
COSTS_FILE = "costs.json"


async def handle_pipeline_run_submission(kind: PipelineRunKind, pipeline_run_id: str, zip_path: str, temp_dir: str) -> None:
    """A background task: a failure is logged, and the run's status, already sent, stands."""
    try:
        with zipfile.ZipFile(zip_path) as zipf:
            context = json.loads(zipf.read(CONTEXT_FILE))
            costs = json.loads(zipf.read(COSTS_FILE))
        recorded = await record_calls(pipeline_run_id, costs["llm_costs"])
        logger.info(f"[{pipeline_run_id}] Recorded {recorded} LLM call(s)")
        issue = ISSUE_READERS[kind](context["data"])
        if issue is not None:
            await upsert_issue(pipeline_run_id, issue.issue_type, [issue.data])
    except Exception:
        logger.exception(f"[{pipeline_run_id}] {kind} submission failed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
