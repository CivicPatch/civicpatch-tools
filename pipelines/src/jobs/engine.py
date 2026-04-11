from typing import Callable, Optional, Dict, Any, TypeVar
from dataclasses import replace
from time import sleep
from domain.workflow_context import WorkflowContext

TContext = TypeVar("TContext", bound=WorkflowContext)
from shared.utils.config_utils import get_job_config
from utils import log_utils
import time
from datetime import datetime, timezone
import services.civicpatch_api as civicpatch_api
import psutil

from jobs.people_collector.schemas import PipelineStatus


class WorkflowError(Exception):
    """Raised when a workflow terminates in ERROR state."""
    def __init__(self, jurisdiction_ocdid: str, context: WorkflowContext):
        self.jurisdiction_ocdid = jurisdiction_ocdid
        self.context = context
        super().__init__(f"Workflow failed for {jurisdiction_ocdid}")


def log_system_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    cpu_percent = psutil.cpu_percent(interval=None)
    print(f"Memory Usage: {memory_info.rss / (1024 * 1024):.2f} MB")
    print(f"CPU Usage: {cpu_percent}%")


async def run_workflow(
    context: TContext,
    logger: log_utils.WorkflowLogger,
    transition_map: Dict[PipelineStatus, Callable[..., Any]],
    persist_fn: Optional[Callable] = None,
) -> TContext:
    ctx = context
    job_config = get_job_config(logger)
    jurisdiction_ocdid = ctx.data.jurisdiction_ocdid

    created_at = time.time()
    ctx = ctx.copy(update={"created_at": created_at, "updated_at": created_at})

    terminal_states = {PipelineStatus.COMPLETED, PipelineStatus.ERROR}

    try:
        while ctx.current_state not in terminal_states:
            log_system_usage()
            try:
                await civicpatch_api.update_job_status(
                    logger, ctx.request_id, ctx.data.jurisdiction_ocdid,
                    status=ctx.current_state.value, progress=ctx.progress
                )
            except Exception as e:
                logger.warning(f"Failed to update job status (non-fatal): {e}")

            transition_fn = transition_map[ctx.current_state]
            ctx, next_state = await transition_fn(job_config, logger, ctx)
            ctx = ctx.copy(update={"current_state": next_state, "updated_at": time.time()})

            if persist_fn:
                persist_fn(ctx)
    finally:
        log_system_usage()
        final_progress = 100 if ctx.current_state == PipelineStatus.COMPLETED else ctx.progress
        try:
            await civicpatch_api.update_job_status(
                logger, ctx.request_id, ctx.data.jurisdiction_ocdid,
                status=ctx.current_state.value, progress=final_progress
            )
        except Exception as e:
            logger.warning(f"Failed to update final job status (non-fatal): {e}")

    if ctx.current_state == PipelineStatus.ERROR:
        raise WorkflowError(jurisdiction_ocdid, ctx)

    return ctx
