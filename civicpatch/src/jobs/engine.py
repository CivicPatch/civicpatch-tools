from typing import Callable, Optional, Dict
from dataclasses import replace
from time import sleep
from domain.workflow_context import WorkflowContext
from shared.utils.config_utils import get_job_config
from utils import log_utils

from jobs.people_collector.schemas import WorkflowStatus
from jobs.registry import (
    register_workflow,
    workflow_stop_requested,
    update_workflow_state,
    unregister_workflow,
)

async def run_workflow(
    context,
    logger: log_utils.WorkflowLogger,
    transition_map: Dict[str, Callable[[WorkflowContext], str]],
    persist_fn: Optional[Callable] = None,
) -> WorkflowContext:
    """
    Run a workflow from its current state until DONE or stop_flag triggers.
    context: WorkflowContext[TData, TState]
    step_runner: function that takes context -> new context
    stop_flag: optional function returning True to interrupt
    persist_fn: optional function to persist context between steps
    """
    ctx = context
    job_config = get_job_config(logger)
    jurisdiction_id = ctx.data.jurisdiction_id

    register_workflow(jurisdiction_id, ctx.current_state)

    while ctx.current_state != WorkflowStatus.DONE: # Note: all workflow state should include DONE
        if workflow_stop_requested(jurisdiction_id):
          ctx = ctx.copy(update={"current_state": WorkflowStatus.DONE})
          break

        transition_fn = transition_map[ctx.current_state]
        ctx, next_state = await transition_fn(job_config, logger, ctx)
        ctx = ctx.copy(update={"current_state": next_state})
        update_workflow_state(jurisdiction_id, ctx.current_state)

        if persist_fn:
            persist_fn(ctx)

    unregister_workflow(jurisdiction_id)

    return ctx
