import asyncio
import json
import traceback
import logging

import httpx

from runners.engine import run_pipeline, PipelineRunError
from runners.people_collector.schemas import (
  PipelineRunConfig,
  PipelineStatus,
  PeopleCollectorData,
  PeopleCollectorContext,
)
from domain.models import Official
from domain.pipeline_run_context import PipelineRunContext
from runners.people_collector.transitions.main import TRANSITION_MAP
from services.github_config_service import make_github_fetcher
from shared.utils import data_path_utils
from shared.utils.config_utils import load_role_config_for_jurisdiction
from shared.utils.github_urls import derive_raw_base_url
from shared.utils.url_utils import same_domain, same_url
from pipelines_environment import get_env_vars
from utils import log_utils
from utils.log_utils import PipelineRunLogger
from utils.url_utils import resolve_redirect

logger = logging.getLogger(__name__)


def initialize_pipeline_run(request_id, jurisdiction_ocdid: str, config: PipelineRunConfig) -> tuple[PeopleCollectorContext, PipelineRunLogger]:
    env = get_env_vars()
    raw_base = derive_raw_base_url(env["OPEN_DATA_REPO_URL"])
    fetch_remote = make_github_fetcher(raw_base)
    try:
        role_config = load_role_config_for_jurisdiction(jurisdiction_ocdid, fetch_remote)
    except Exception as e:
        logger.warning("Could not load remote role config for %s, falling back to local: %s", jurisdiction_ocdid, e)
        role_config = None

    context = PeopleCollectorContext(
        request_id=request_id,
        current_state=PipelineStatus.INIT,
        data=PeopleCollectorData(
          jurisdiction_ocdid=jurisdiction_ocdid,
          config=config,
          role_config=role_config,
        ),
    )
    pipeline_run_logger = log_utils.get_pipeline_run_logger(jurisdiction_ocdid)
    role_names = [r.role for r in role_config.roles] if role_config else []
    pipeline_run_logger.info(f"Role config: roles={role_names}")
    return context, pipeline_run_logger


async def start(request_id: str, jurisdiction_ocdid: str, config: PipelineRunConfig) -> PeopleCollectorContext:
    """Entry point for people collector. Logs errors and re-raises."""
    resolved_url = await resolve_redirect(config.url)
    if not same_url(config.url, resolved_url):
        logger.info("Canonical URL redirected: %s -> %s", config.url, resolved_url)
        if not same_domain(config.url, resolved_url):
            logger.info("Domain redirected: %s -> %s", config.url, resolved_url)
        config = config.model_copy(update={"url": resolved_url})

    context, pipeline_run_logger = initialize_pipeline_run(request_id, jurisdiction_ocdid, config)
    env = get_env_vars()

    try:
        async with httpx.AsyncClient(headers={"Authorization": env["SERVICE_API_KEY"]}, timeout=120.0) as api_client:
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


async def start_threaded(request_id, jurisdiction_ocdid, config):
    """For API: Run the start coroutine in a separate thread."""
    def run_start():
        asyncio.run(start(request_id, jurisdiction_ocdid, config))

    await asyncio.to_thread(run_start)


def persist_context(context: PeopleCollectorContext):
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    context_file_path = data_path_utils.get_pipeline_run_context_file_path(jurisdiction_ocdid)
    serialized_data = context.model_dump_json(indent=4, ensure_ascii=False)
    with open(context_file_path, "w") as f:
        f.write(serialized_data)
