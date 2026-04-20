import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompts
from runners.people_collector.schemas import FindJurisdictionUrlStep, PeopleCollectorContext
from utils import log_utils


async def find_jurisdiction_url(context: PeopleCollectorContext) -> FindJurisdictionUrlStep:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info("find_jurisdiction_url: asking Gemini for real URL")

    prompt = google_gemini_prompts.find_jurisdiction_url_prompt(
        context.data.jurisdiction_ocdid,
        context.data.config.name or "",
        stale_url=context.data.config.url,
    )

    # with_search=True returns a plain dict via parse_raw_response
    response = await google_gemini_llm.run_prompt(
        context.request_id,
        context.data.jurisdiction_ocdid,
        prompt,
        with_search=True,
    )

    discovered_url = (response or {}).get("url")
    logger.info(f"find_jurisdiction_url: discovered_url={discovered_url!r}")
    return FindJurisdictionUrlStep(discovered_url=discovered_url)
