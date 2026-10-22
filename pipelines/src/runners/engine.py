import traceback
import traceback
from typing import Callable, Optional, Dict, Any, TypeVar
from dataclasses import dataclass, replace
from enum import StrEnum
from time import sleep
from domain.pipeline_run_context import PipelineRunContext

TContext = TypeVar("TContext", bound=PipelineRunContext)
from shared.utils.config_utils import load_pipeline_run_limits
from utils import log_utils
import time
from datetime import datetime, timezone
import httpx
import services.civicpatch_api as civicpatch_api
from shared.utils.statuses import PipelineRunStatus
import psutil


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
    ctx = ctx.copy(update={"created_at": created_at, "updated_at": created_at})

    terminal = set(terminal_states(machine.transitions))

    try:
        while ctx.current_state not in terminal:
            log_system_usage()
            try:
                current_status = await civicpatch_api.fetch_pipeline_run_status(api_client, logger, ctx.pipeline_run_id)
                if current_status == PipelineRunStatus.CANCELLED:
                    logger.info(f"Pipeline run {ctx.pipeline_run_id} cancelled — stopping.")
                    ctx = ctx.copy(
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
                ctx = ctx.copy(update={"current_state": PipelineRunStatus.SEND_ERROR, "updated_at": time.time()})
            else:
                # Outside the except: a step failing ends a run, a step naming an impossible
                # state is a bug, and SEND_ERROR would hide the second as the first.
                if next_state not in next_states(machine.transitions, current):
                    raise IllegalTransition(current, next_state)
                ctx = ctx.copy(update={"current_state": next_state, "updated_at": time.time()})

            if persist_fn:
                persist_fn(ctx)
    finally:
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

    if ctx.current_state == PipelineRunStatus.ERROR:
        raise PipelineRunError(jurisdiction_ocdid, ctx)

    return ctx
