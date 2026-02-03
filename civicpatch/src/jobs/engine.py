from typing import Callable, Optional, Dict
from dataclasses import replace
from time import sleep
from domain.workflow_context import WorkflowContext
from shared.utils.config_utils import get_job_config
from utils import log_utils
import time
from datetime import datetime, timezone
import services.civicpatch_api as civicpatch_api

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
    jurisdiction_ocdid = ctx.data.jurisdiction_ocdid
    
    created_at = time.time()
    ctx = ctx.copy(update={
        "created_time": created_at,
        "updated_time": created_at
    })

    register_workflow(jurisdiction_ocdid, ctx.current_state)

    while ctx.current_state not in [WorkflowStatus.DONE]: # Note: all workflow state should include DONE
        await civicpatch_api.update_job_status(
            ctx.request_id,
            ctx.data.jurisdiction_ocdid,
            status=ctx.current_state.value,
            progress=ctx.progress
        )
        if workflow_stop_requested(jurisdiction_ocdid):
          ctx = ctx.copy(update={
              "current_state": ctx.current_state,
              "updated_at": time.time()
          })
          break

        transition_fn = transition_map[ctx.current_state]
        ctx, next_state = await transition_fn(job_config, logger, ctx)
        ctx = ctx.copy(update={
            "current_state": next_state,
            "updated_at": time.time()
        })
        update_workflow_state(jurisdiction_ocdid, ctx.current_state)

        if persist_fn:
            persist_fn(ctx)

    await civicpatch_api.update_job_status(
        ctx.request_id,
        ctx.data.jurisdiction_ocdid,
        status=ctx.current_state.value,
        progress=100
    )
    unregister_workflow(jurisdiction_ocdid)

    return ctx
