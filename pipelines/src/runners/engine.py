import traceback
import traceback
from typing import Callable, Optional, Dict, Any, TypeVar
from dataclasses import replace
from time import sleep
from domain.pipeline_run_context import PipelineRunContext

TContext = TypeVar("TContext", bound=PipelineRunContext)
from shared.utils.config_utils import load_job_config
from utils import log_utils
import time
from datetime import datetime, timezone
import httpx
import services.civicpatch_api as civicpatch_api
from shared.utils.statuses import PipelineRunStatus
import psutil

from runners.people_collector.schemas import PipelineStatus


class PipelineRunError(Exception):
    """Raised when a pipeline run terminates in ERROR state."""
    def __init__(self, jurisdiction_ocdid: str, context: PipelineRunContext):
        self.jurisdiction_ocdid = jurisdiction_ocdid
        self.context = context
        super().__init__(f"Pipeline run failed for {jurisdiction_ocdid}")


def log_system_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    cpu_percent = psutil.cpu_percent(interval=None)
    print(f"Memory Usage: {memory_info.rss / (1024 * 1024):.2f} MB")
    print(f"CPU Usage: {cpu_percent}%")


async def run_pipeline(
    context: TContext,
    logger: log_utils.PipelineRunLogger,
    transition_map: Dict[PipelineStatus, Callable[..., Any]],
    api_client: httpx.AsyncClient,
    persist_fn: Optional[Callable] = None,
) -> TContext:
    ctx = context
    job_config = load_job_config(logger)
    jurisdiction_ocdid = ctx.data.jurisdiction_ocdid

    created_at = time.time()
    ctx = ctx.copy(update={"created_at": created_at, "updated_at": created_at})

    terminal_states = {PipelineStatus.SUCCESS, PipelineStatus.ERROR}

    try:
        while ctx.current_state not in terminal_states:
            log_system_usage()
            try:
                current_status = await civicpatch_api.fetch_pipeline_run_status(api_client, ctx.request_id)
                if current_status == PipelineRunStatus.CANCELLED:
                    logger.info(f"Pipeline run {ctx.request_id} cancelled — stopping.")
                    return ctx
            except Exception as e:
                logger.warning(f"Failed to check cancellation status (non-fatal): {e}")
            try:
                await civicpatch_api.update_pipeline_run_status(
                    api_client, logger, ctx.request_id, ctx.data.jurisdiction_ocdid,
                    status=ctx.current_state.value, progress=ctx.progress,
                    error_type=getattr(ctx.data, 'error_step', None),
                )
            except Exception as e:
                logger.warning(f"Failed to update job status (non-fatal): {e}")

            transition_fn = transition_map[ctx.current_state]
            try:
                ctx, next_state = await transition_fn(job_config, logger, ctx, api_client)
                ctx = ctx.copy(update={"current_state": next_state, "updated_at": time.time()})
            except Exception as e:
                logger.error(
                    f"Unhandled exception in {ctx.current_state} transition: {e}\n"
                    f"{traceback.format_exc()}"
                )
                ctx = ctx.copy(update={"current_state": PipelineStatus.SEND_ERROR, "updated_at": time.time()})

            if persist_fn:
                persist_fn(ctx)
    finally:
        log_system_usage()
        final_progress = 100 if ctx.current_state == PipelineStatus.SUCCESS else ctx.progress
        try:
            await civicpatch_api.update_pipeline_run_status(
                api_client, logger, ctx.request_id, ctx.data.jurisdiction_ocdid,
                status=ctx.current_state.value, progress=final_progress,
                error_type=getattr(ctx.data, 'error_step', None),
            )
        except Exception as e:
            logger.warning(f"Failed to update final job status (non-fatal): {e}")

    if ctx.current_state == PipelineStatus.ERROR:
        raise PipelineRunError(jurisdiction_ocdid, ctx)

    return ctx
