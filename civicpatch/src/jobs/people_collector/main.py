import asyncio
from jobs.engine import run_workflow
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

def initialize_workflow(request_id, jurisdiction_ocdid: str, config: WorkflowConfig) -> PeopleCollectorContext:
    context = PeopleCollectorContext(
        request_id=request_id,
        current_state=WorkflowStatus.INIT,
        data=PeopleCollectorData(
          jurisdiction_ocdid=jurisdiction_ocdid,
          config=config,
        ),
    )
    logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    RUNNING_WORKFLOWS[jurisdiction_ocdid] = WorkflowEntry(
        current_state=context.current_state,
        stop_flag=False
    )
    return context, logger

async def start(request_id: str, jurisdiction_ocdid: str, config: WorkflowConfig) -> PeopleCollectorContext:
    """For cli"""
    context, logger = initialize_workflow(request_id, jurisdiction_ocdid, config)

    return await run_workflow(
        context,
        logger,
        TRANSITION_MAP,
        persist_context
    )

async def start_threaded(request_id, jurisdiction_ocdid, config):
    """For API: Run the start coroutine in a separate thread."""
    def run_start():
        asyncio.run(start(request_id, jurisdiction_ocdid, config))

    await asyncio.to_thread(run_start)

#def resume_people_collector(context: PeopleCollectorContext, stop_flag=None, persist_fn=None):
#    """Resume existing workflow"""
#    return run_workflow(context, step_runner, stop_flag=stop_flag, persist_fn=persist_fn)

def stop(context: PeopleCollectorContext) -> PeopleCollectorContext:
    stop_workflow(context.data.jurisdiction_ocdid)

def persist_context(context: PeopleCollectorContext):
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    context_file_path = data_path_utils.get_workflow_context_file_path(jurisdiction_ocdid)
    serialized_data = context.model_dump_json(indent=4, ensure_ascii=False)
    with open(context_file_path, "w") as f:
        f.write(serialized_data)
