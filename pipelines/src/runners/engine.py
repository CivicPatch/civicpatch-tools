import traceback
import traceback
from typing import Callable, Optional, Dict, Any, TypeVar
from dataclasses import dataclass, replace
from enum import StrEnum
from time import sleep
from domain.pipeline_run_context import PipelineRunContext

TContext = TypeVar("TContext", bound=PipelineRunContext)
from shared.utils.config_utils import load_pipeline_run_limits
from utils import cost_utils, file_utils, log_utils
import time
from datetime import datetime, timezone
import httpx
import services.civicpatch_api as civicpatch_api
from shared.utils.run_reports import RunFailure
from shared.utils.statuses import PipelineRunStatus
import psutil


# A failure's message is kept for a person reading the issue, not as a log.
FAILURE_ERROR_CHARS = 500

# A state is a pipeline's own step or a shared lifecycle state: a member of either StrEnum.
Transitions = dict[StrEnum, frozenset[StrEnum]]


def terminal_states(transitions: Transitions) -> tuple[StrEnum, ...]:
    return tuple(status for status, allowed in transitions.items() if not allowed)


def next_states(transitions: Transitions, current: StrEnum) -> frozenset[StrEnum]:
    """Where a run may go from here in its pipeline's graph. Empty for a terminal state."""
    allowed = transitions.get(current, frozenset())
    if not allowed:
        return allowed
    # A handler that raises is sent to SEND_ERROR, and cancellation is polled each loop, so
    # both are reachable from every state rather than chosen by a step.
    return allowed | {PipelineRunStatus.SEND_ERROR, PipelineRunStatus.CANCELLED}


@dataclass(frozen=True)
class Machine:
    """A pipeline as the engine runs it: its graph, and who handles each state in it. A dataclass,
    not a model: validation would coerce each StrEnum key against the bare base class."""

    transitions: Transitions
    handlers: Dict[StrEnum, Callable[..., Any]]
    # The engine sends the run's context and costs to cp.org when it ends. Pipeline 3 sends its own.
    submits_context: bool


class IllegalTransition(Exception):
    """A step returned a state its pipeline's graph does not allow from this one."""
    def __init__(self, current: StrEnum, requested: StrEnum):
        self.current = current
        self.requested = requested
        super().__init__(f"{current} -> {requested} is not a legal transition")


class PipelineRunError(Exception):
    """Raised when a pipeline run terminates in ERROR state."""
    def __init__(self, jurisdiction_ocdid: str, context: PipelineRunContext):
        self.jurisdiction_ocdid = jurisdiction_ocdid
        self.context = context
        super().__init__(f"Pipeline run failed for {jurisdiction_ocdid}")


async def _finish(ctx: PipelineRunContext, logger: log_utils.PipelineRunLogger, machine: Machine, api_client: httpx.AsyncClient) -> None:
    """The run's last word, whatever ended it: its final status, then its context where the machine sends one."""
    log_system_usage()
    final_progress = 100 if ctx.current_state == PipelineRunStatus.SUCCESS else ctx.progress
    try:
        await civicpatch_api.update_pipeline_run_status(
            api_client, logger, ctx.pipeline_run_id, ctx.data.jurisdiction_ocdid,
            status=ctx.current_state.value, progress=final_progress,
            error_type=getattr(ctx.data, 'error_step', None),
        )
    except Exception as e:
        logger.warning(f"Failed to update final job status (non-fatal): {e}")
    if machine.submits_context:
        await _submit_context(ctx, logger, api_client)


async def _submit_context(ctx: PipelineRunContext, logger: log_utils.PipelineRunLogger, api_client: httpx.AsyncClient) -> None:
    """cp.org files the run's issues and records its costs from this. A failed send leaves the run's
    status standing, as a failed status update does."""
    jurisdiction_ocdid = ctx.data.jurisdiction_ocdid
    zip_path = file_utils.zip_run_context(
        ctx.pipeline_run_id, jurisdiction_ocdid, ctx.model_dump_json(), cost_utils.get_cost_tracker(ctx.pipeline_run_id)
    )
    try:
        response = await civicpatch_api.submit_job_artifacts(
            api_client, ctx.pipeline_run_id, jurisdiction_ocdid, zip_path, pipeline_run_status=ctx.current_state.value
        )
        if not response.is_success:
            logger.warning(f"Context submit answered {response.status_code} (non-fatal): {response.text[:200]}")
    except httpx.HTTPError as e:
        logger.warning(f"Failed to submit the run's context (non-fatal): {e}")
    finally:
        cost_utils.reset_cost_tracker(ctx.pipeline_run_id)


def log_system_usage():
    process = psutil.Process()
    memory_info = process.memory_info()
    cpu_percent = psutil.cpu_percent(interval=None)
    print(f"Memory Usage: {memory_info.rss / (1024 * 1024):.2f} MB")
    print(f"CPU Usage: {cpu_percent}%")


async def run_pipeline(
    context: TContext,
    logger: log_utils.PipelineRunLogger,
    machine: Machine,
    api_client: httpx.AsyncClient,
    persist_fn: Optional[Callable] = None,
) -> TContext:
    ctx = context
    # The context carries the state's ceiling when a dispatch resolved one; otherwise this
    # is `pipeline.yml`'s default, unchanged.
    limits = load_pipeline_run_limits(logger, context.data.config.pipeline_run_cap_usd)
    jurisdiction_ocdid = ctx.data.jurisdiction_ocdid

    created_at = time.time()
    ctx = ctx.model_copy(update={"created_at": created_at, "updated_at": created_at})

    terminal = set(terminal_states(machine.transitions))

    try:
        while ctx.current_state not in terminal:
            log_system_usage()
            try:
                current_status = await civicpatch_api.fetch_pipeline_run_status(api_client, logger, ctx.pipeline_run_id)
                if current_status == PipelineRunStatus.CANCELLED:
                    logger.info(f"Pipeline run {ctx.pipeline_run_id} cancelled — stopping.")
                    ctx = ctx.model_copy(
                        update={
                            "current_state": PipelineRunStatus.CANCELLED,
                            "updated_at": time.time(),
                        }
                    )
                    break
            except Exception as e:
                logger.warning(f"Failed to check cancellation status (non-fatal): {e}")
            try:
                await civicpatch_api.update_pipeline_run_status(
                    api_client, logger, ctx.pipeline_run_id, ctx.data.jurisdiction_ocdid,
                    status=ctx.current_state.value, progress=ctx.progress,
                    error_type=getattr(ctx.data, 'error_step', None),
                    error_detail=getattr(ctx.data, 'error_detail', None),
                )
            except Exception as e:
                logger.warning(f"Failed to update job status (non-fatal): {e}")

            current = ctx.current_state
            transition_fn = machine.handlers[current]
            try:
                ctx, next_state = await transition_fn(limits, logger, ctx, api_client)
            except Exception as e:
                logger.error(
                    f"Unhandled exception in {current} transition: {e}\n"
                    f"{traceback.format_exc()}"
                )
                failure = RunFailure(failed_state=str(current), error=f"{type(e).__name__}: {e}"[:FAILURE_ERROR_CHARS])
                ctx = ctx.model_copy(update={"current_state": PipelineRunStatus.SEND_ERROR, "updated_at": time.time(), "failure": failure})
            else:
                # Outside the except: a step failing ends a run, a step naming an impossible
                # state is a bug, and SEND_ERROR would hide the second as the first.
                if next_state not in next_states(machine.transitions, current):
                    raise IllegalTransition(current, next_state)
                ctx = ctx.model_copy(update={"current_state": next_state, "updated_at": time.time()})

            if persist_fn:
                persist_fn(ctx)
    finally:
        await _finish(ctx, logger, machine, api_client)

    if ctx.current_state == PipelineRunStatus.ERROR:
        raise PipelineRunError(jurisdiction_ocdid, ctx)

    return ctx
