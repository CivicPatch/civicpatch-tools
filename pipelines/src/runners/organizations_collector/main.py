import logging

import httpx
from pipelines_environment import get_env_vars
from runners.engine import Machine, PipelineRunError, run_pipeline
from runners.organizations_collector.schemas import (
    OrganizationsCollectorConfig,
    OrganizationsCollectorContext,
    OrganizationsCollectorData,
)
from runners.organizations_collector.transitions.graph import ORGANIZATIONS_COLLECTOR_TRANSITIONS
from runners.organizations_collector.transitions.main import TRANSITION_MAP
from shared.utils.statuses import PipelineRunStatus
from utils import log_utils

logger = logging.getLogger(__name__)

MACHINE = Machine(transitions=ORGANIZATIONS_COLLECTOR_TRANSITIONS, handlers=TRANSITION_MAP)


async def start(
    pipeline_run_id: str, jurisdiction_ocdid: str, config: OrganizationsCollectorConfig
) -> OrganizationsCollectorContext:
    """No `persist_fn`: the context, and the law text it holds between steps, is never written to disk."""
    context = OrganizationsCollectorContext(
        pipeline_run_id=pipeline_run_id,
        current_state=PipelineRunStatus.INIT,
        data=OrganizationsCollectorData(jurisdiction_ocdid=jurisdiction_ocdid, config=config),
    )
    env = get_env_vars()
    async with httpx.AsyncClient(headers={"Authorization": env["SERVICE_API_KEY"]}, timeout=60.0) as api_client:
        try:
            return await run_pipeline(context, log_utils.get_pipeline_run_logger(jurisdiction_ocdid), MACHINE, api_client)
        except PipelineRunError as e:
            logger.error(f"Organizations collection failed for {e.jurisdiction_ocdid}: {e}")
            raise
