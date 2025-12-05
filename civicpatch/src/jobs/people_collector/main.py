import asyncio
from jobs.engine import run_workflow
from jobs.people_collector.schemas import (
  WorkflowConfig,
  WorkflowStatus,
  PeopleCollectorData,
  PeopleCollectorContext,
)
from domain.workflow_context import WorkflowContext
from jobs.people_collector.transitions.main import TRANSITION_MAP
from shared.utils import data_path_utils
from utils import log_utils
from jobs.registry import RUNNING_WORKFLOWS, WorkflowEntry, stop_workflow
from threading import Thread

def initialize_workflow(request_id, jurisdiction_id: str, config: WorkflowConfig) -> PeopleCollectorContext:
    context = PeopleCollectorContext(
        request_id=request_id,
        current_state=WorkflowStatus.INIT,
        data=PeopleCollectorData(
          jurisdiction_id=jurisdiction_id,
          config=config,
          identities=config.identities or {}
        ),
    )
    logger = log_utils.get_workflow_logger(jurisdiction_id)
    RUNNING_WORKFLOWS[jurisdiction_id] = WorkflowEntry(
        current_state=context.current_state,
        stop_flag=False
    )
    return context, logger

async def start(request_id: str, jurisdiction_id: str, config: WorkflowConfig) -> PeopleCollectorContext:
    """For cli"""
    context, logger = initialize_workflow(request_id, jurisdiction_id, config)

    return await run_workflow(
        context,
        logger,
        TRANSITION_MAP,
        persist_context
    )

def start_in_background(request_id: str, jurisdiction_id: str, config: WorkflowConfig) -> PeopleCollectorContext:
    """For fastapi"""
    context, logger = initialize_workflow(request_id, jurisdiction_id, config)

    def target():
        try:
            asyncio.run(
                run_workflow(
                    context,
                    logger,
                    TRANSITION_MAP,
                    persist_context
                )
            )
        except Exception as e:
            logger.error("Workflow failed")

    thread = Thread(target=target, daemon=True).start()
    return context


#def resume_people_collector(context: PeopleCollectorContext, stop_flag=None, persist_fn=None):
#    """Resume existing workflow"""
#    return run_workflow(context, step_runner, stop_flag=stop_flag, persist_fn=persist_fn)

def stop(context: PeopleCollectorContext) -> PeopleCollectorContext:
    stop_workflow(context.data.jurisdiction_id)

def persist_context(context: PeopleCollectorContext):
    jurisdiction_id = context.data.jurisdiction_id
    context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)
    serialized_data = context.model_dump_json(indent=4, ensure_ascii=False)
    with open(context_file_path, "w") as f:
        f.write(serialized_data)
