"""When cp.org hands a run government form choices, ask Gemini to pick one and save the answer to
cp.org, which keeps it only while no form is set. This run carries on without a government form
either way."""

from typing import List

import httpx
import services.civicpatch_api as civicpatch_api
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
from runners.pipeline03_people_collector.schemas import PeopleCollectorContext
from shared.schemas import GovernmentForm, JurisdictionExtras, JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid


def answered_government_form(answer: dict, allowed: List[GovernmentForm]) -> GovernmentForm | None:
    """The government form the model picked, if it is one it was offered."""
    for government_form in allowed:
        if answer.get("government_form") == government_form.value:
            return government_form
    return None


def government_form_prompt(jurisdiction_ocdid: str, name: str, allowed: List[GovernmentForm]) -> str:
    if parse_jurisdiction_ocdid(jurisdiction_ocdid).level == JurisdictionLevel.COUNTIES:
        return google_gemini_prompt.county_government_form_prompt(jurisdiction_ocdid, name, allowed)
    return google_gemini_prompt.municipal_government_form_prompt(jurisdiction_ocdid, name, allowed)


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
        logger.warning(f"government_form: no allowed government form in the answer {answer!r}; not saving")
        return
    try:
        await civicpatch_api.patch_jurisdiction_extras(
            api_client, jurisdiction_ocdid, JurisdictionExtras(extras_government_form=government_form)
        )
    except httpx.HTTPStatusError as exc:
        # The next run asks again; a failed save is no reason to fail the scrape.
        logger.warning(f"government_form: cp.org refused it: {exc}")
        return
    logger.info(f"government_form: saved {government_form.value}")
