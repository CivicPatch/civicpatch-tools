"""When cp.org hands a run government form choices, ask Gemini to pick one and send the answer back as a pull
request. cp.org decides whether to ask; a person merges or closes the PR; this run carries on
without a government form either way."""

import re
from typing import List
from urllib.parse import urlparse

import httpx
import services.civicpatch_api as civicpatch_api
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
from runners.people_collector.schemas import PeopleCollectorContext
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid

# Grounded answers cite Google redirect links that expire, useless in a PR a person reads later.
# Only this host is followed: the URL comes from the model, so anything else is never requested.
_GROUNDING_REDIRECT_HOST = "vertexaisearch.cloud.google.com"
_URL = re.compile(r"https?://[^\s,;]+")


def answered_government_form(answer: dict, allowed: List[GovernmentForm]) -> GovernmentForm | None:
    """The government form the model picked, if it is one it was offered."""
    for government_form in allowed:
        if answer.get("government_form") == government_form.value:
            return government_form
    return None


def source_urls(answer: dict) -> List[str]:
    """Every URL in `source`: models sometimes pack several into one string."""
    return _URL.findall(str(answer.get("source") or ""))


def government_form_prompt(jurisdiction_ocdid: str, name: str, allowed: List[GovernmentForm]) -> str:
    if parse_jurisdiction_ocdid(jurisdiction_ocdid).level == JurisdictionLevel.COUNTIES:
        return google_gemini_prompt.county_government_form_prompt(jurisdiction_ocdid, name, allowed)
    return google_gemini_prompt.municipal_government_form_prompt(jurisdiction_ocdid, name, allowed)


async def resolve_redirects(urls: List[str]) -> List[str]:
    """Each grounding redirect replaced by where it points; one that does not redirect is dropped.
    Its own client: the API client carries the service key, which must not go to Google."""
    resolved = []
    async with httpx.AsyncClient(timeout=10) as client:
        for url in urls:
            if urlparse(url).hostname != _GROUNDING_REDIRECT_HOST:
                resolved.append(url)
                continue
            try:
                location = (await client.head(url, follow_redirects=False)).headers.get("location")
            except httpx.HTTPError:
                continue
            if location:
                resolved.append(location)
    return resolved


async def request_government_form(
    context: PeopleCollectorContext, api_client: httpx.AsyncClient, logger
) -> None:
    config = context.data.config
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    answer = await google_gemini_llm.run_prompt(
        context.pipeline_run_id,
        jurisdiction_ocdid,
        government_form_prompt(jurisdiction_ocdid, config.name or "", config.government_form_choices),
        prompt_name="government_form",
    )
    government_form = answered_government_form(answer or {}, config.government_form_choices)
    if government_form is None:
        logger.warning(f"government_form: no allowed government form in the answer {answer!r}; not proposing")
        return
    sources = await resolve_redirects(source_urls(answer or {}))
    try:
        opened = await civicpatch_api.open_jurisdiction_pull_request(api_client, jurisdiction_ocdid, government_form, sources)
    except httpx.HTTPStatusError as exc:
        # The next run asks again; a failed proposal is no reason to fail the scrape.
        logger.warning(f"government_form: cp.org refused the pull request: {exc}")
        return
    if opened is None:
        logger.info("government_form: a pull request is already open; not proposing again")
        return
    logger.info(f"government_form: proposed {government_form.value} in {opened['pull_request_url']}")
