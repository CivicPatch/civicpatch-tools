import pathlib

import services.google_gemini.llm as google_gemini_llm
from services.google_gemini.llm import FIND_JURISDICTION_URL_MODEL_FALLBACKS
import services.google_gemini.prompts as google_gemini_prompts
import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from runners.people_collector.schemas import (
    FindJurisdictionUrlStep,
    LinkStatus,
    OfficialJurisdictionUrlResponseSchema,
    PeopleCollectorContext,
)
from shared.utils import data_path_utils
from utils import log_utils


async def find_jurisdiction_url(context: PeopleCollectorContext) -> FindJurisdictionUrlStep:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)

    root_link = context.data.frontier.get(context.data.config.url)
    if root_link and root_link.status not in (LinkStatus.ERROR.value, LinkStatus.PREPROCESSED_NO_CONTENT.value):
        content_path = (
            pathlib.Path(data_path_utils.get_cache_path(context.data.jurisdiction_ocdid))
            / root_link.folder_name
            / "preprocessed.md"
        )
        if content_path.exists():
            content = content_path.read_text(encoding="utf-8")
            if content.strip():
                check = await open_router_llm.run_prompt(
                    context.changeset_id,
                    context.data.jurisdiction_ocdid,
                    open_router_prompts.is_official_jurisdiction_url_prompt(),
                    response_schema=OfficialJurisdictionUrlResponseSchema,
                    content=content,
                )
                if check.is_official_jurisdiction_url:
                    logger.info("find_jurisdiction_url: root page confirmed official, no URL change needed")
                    return FindJurisdictionUrlStep(discovered_url=context.data.config.url)

    logger.info("find_jurisdiction_url: asking Gemini for real URL")
    prompt = google_gemini_prompts.find_jurisdiction_url_prompt(
        context.data.jurisdiction_ocdid,
        context.data.config.name or "",
        stale_url=context.data.config.url,
    )
    response = await google_gemini_llm.run_prompt(
        context.changeset_id,
        context.data.jurisdiction_ocdid,
        prompt,
        with_search=True,
        model_fallbacks=FIND_JURISDICTION_URL_MODEL_FALLBACKS,
    )
    discovered_url = (response or {}).get("url")
    logger.info(f"find_jurisdiction_url: discovered_url={discovered_url!r}")
    return FindJurisdictionUrlStep(discovered_url=discovered_url)
