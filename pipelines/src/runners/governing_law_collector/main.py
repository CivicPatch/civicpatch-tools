import logging

import httpx
from pipelines_environment import get_env_vars
from runners.engine import Machine, PipelineRunError, run_pipeline
from runners.governing_law_collector.schemas import (
    GoverningLawCollectorConfig,
    GoverningLawCollectorContext,
    GoverningLawCollectorData,
)
from runners.governing_law_collector.transitions.graph import GOVERNING_LAW_COLLECTOR_TRANSITIONS
from runners.governing_law_collector.transitions.main import TRANSITION_MAP
from shared.utils.statuses import PipelineRunStatus
from utils import log_utils

logger = logging.getLogger(__name__)

MACHINE = Machine(transitions=GOVERNING_LAW_COLLECTOR_TRANSITIONS, handlers=TRANSITION_MAP)


async def start(
    pipeline_run_id: str, jurisdiction_ocdid: str, config: GoverningLawCollectorConfig
) -> GoverningLawCollectorContext:
    """No `persist_fn`: the context, and the raw page it briefly holds, is never written to disk."""
    context = GoverningLawCollectorContext(
        pipeline_run_id=pipeline_run_id,
        current_state=PipelineRunStatus.INIT,
        data=GoverningLawCollectorData(jurisdiction_ocdid=jurisdiction_ocdid, config=config),
    )
    env = get_env_vars()
    async with httpx.AsyncClient(headers={"Authorization": env["SERVICE_API_KEY"]}, timeout=60.0) as api_client:
        try:
            return await run_pipeline(context, log_utils.get_pipeline_run_logger(jurisdiction_ocdid), MACHINE, api_client)
        except PipelineRunError as e:
            logger.error(f"Governing law collection failed for {e.jurisdiction_ocdid}: {e}")
            raise
