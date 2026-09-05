import asyncio
import logging
import traceback

import httpx
from pipelines_environment import get_env_vars
from runners.engine import PipelineRunError, run_pipeline
from runners.people_collector.schemas import (
    PeopleCollectorContext,
    PeopleCollectorData,
    PipelineRunConfig,
    PipelineStatus,
)
from runners.people_collector.transitions.main import TRANSITION_MAP
from services.browser import resolve_redirect
from services.civicpatch_api import get_role_config
from shared.utils import data_path_utils
from shared.utils.url_utils import same_domain, same_url
from utils import log_utils
from utils.log_utils import PipelineRunLogger

logger = logging.getLogger(__name__)


def initialize_pipeline_run(
    pipeline_run_id, jurisdiction_ocdid: str, config: PipelineRunConfig
) -> tuple[PeopleCollectorContext, PipelineRunLogger]:
    pipeline_run_logger = log_utils.get_pipeline_run_logger(jurisdiction_ocdid)
    context = PeopleCollectorContext(
        pipeline_run_id=pipeline_run_id,
        current_state=PipelineStatus.INIT,
        data=PeopleCollectorData(
            jurisdiction_ocdid=jurisdiction_ocdid,
            config=config,
            role_config=None,
        ),
    )
    return context, pipeline_run_logger


async def start(
    pipeline_run_id: str, jurisdiction_ocdid: str, config: PipelineRunConfig
) -> PeopleCollectorContext:
    """Entry point for people collector. Logs errors and re-raises."""
    resolved_url = await resolve_redirect(config.url)
    if not same_url(config.url, resolved_url):
        logger.info("Canonical URL redirected: %s -> %s", config.url, resolved_url)
        if not same_domain(config.url, resolved_url):
            logger.info("Domain redirected: %s -> %s", config.url, resolved_url)
        config = config.model_copy(update={"url": resolved_url})

    context, pipeline_run_logger = initialize_pipeline_run(
        pipeline_run_id, jurisdiction_ocdid, config
    )
    context.data.role_config = await get_role_config(pipeline_run_logger)
    env = get_env_vars()

    try:
        async with httpx.AsyncClient(
            headers={"Authorization": env["SERVICE_API_KEY"]}, timeout=120.0
        ) as api_client:
            return await run_pipeline(
                context,
                pipeline_run_logger,
                TRANSITION_MAP,
                api_client,
                persist_context,
            )
    except PipelineRunError as e:
        logger.error(f"Pipeline failed for {e.jurisdiction_ocdid}: {e}")
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error in pipeline for {jurisdiction_ocdid}: {e}\n"
            f"{traceback.format_exc()}"
        )
        raise


async def start_threaded(pipeline_run_id, jurisdiction_ocdid, config):
    """For API: Run the start coroutine in a separate thread."""

    def run_start():
        asyncio.run(start(pipeline_run_id, jurisdiction_ocdid, config))

    await asyncio.to_thread(run_start)


def persist_context(context: PeopleCollectorContext):
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    context_file_path = data_path_utils.get_pipeline_run_context_file_path(
        jurisdiction_ocdid
    )
    serialized_data = context.model_dump_json(indent=4, ensure_ascii=False)
    with open(context_file_path, "w") as f:
        f.write(serialized_data)
