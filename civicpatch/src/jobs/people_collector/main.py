import asyncio
import traceback
import logging

from jobs.engine import run_workflow, WorkflowError
from jobs.people_collector.schemas import (
  WorkflowConfig,
  WorkflowStatus,
  PeopleCollectorData,
  PeopleCollectorContext,
)
from domain.models import Official
from domain.workflow_context import WorkflowContext
from jobs.people_collector.transitions.main import TRANSITION_MAP
from shared.utils import data_path_utils
from utils import log_utils
from jobs.registry import RUNNING_WORKFLOWS, WorkflowEntry, stop_workflow

logger = logging.getLogger(__name__)


def initialize_workflow(request_id, jurisdiction_ocdid: str, config: WorkflowConfig) -> PeopleCollectorContext:
    context = PeopleCollectorContext(
        request_id=request_id,
        current_state=WorkflowStatus.INIT,
        data=PeopleCollectorData(
          jurisdiction_ocdid=jurisdiction_ocdid,
          config=config,
        ),
    )
    workflow_logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    RUNNING_WORKFLOWS[jurisdiction_ocdid] = WorkflowEntry(
        current_state=context.current_state,
        stop_flag=False
    )
    return context, workflow_logger


async def start(request_id: str, jurisdiction_ocdid: str, config: WorkflowConfig) -> PeopleCollectorContext:
    """Entry point for people collector. Logs errors and re-raises."""
    context, workflow_logger = initialize_workflow(request_id, jurisdiction_ocdid, config)

    try:
        return await run_workflow(
            context,
            workflow_logger,
            TRANSITION_MAP,
            persist_context
        )
    except WorkflowError as e:
        logger.error(f"Pipeline failed for {e.jurisdiction_ocdid}: {e}")
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error in pipeline for {jurisdiction_ocdid}: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise


async def start_threaded(request_id, jurisdiction_ocdid, config):
    """For API: Run the start coroutine in a separate thread."""
    def run_start():
        asyncio.run(start(request_id, jurisdiction_ocdid, config))

    await asyncio.to_thread(run_start)


def stop(context: PeopleCollectorContext) -> PeopleCollectorContext:
    stop_workflow(context.data.jurisdiction_ocdid)


def persist_context(context: PeopleCollectorContext):
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    context_file_path = data_path_utils.get_workflow_context_file_path(jurisdiction_ocdid)
    serialized_data = context.model_dump_json(indent=4, ensure_ascii=False)
    with open(context_file_path, "w") as f:
        f.write(serialized_data)

