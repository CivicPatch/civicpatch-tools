"""One handler per state of ORGANIZATIONS_COLLECTOR_TRANSITIONS. Each takes the context and
answers it with the next state; the engine checks the answer against the graph. Plan 2's 2.11
to 2.15 fill in SELECT_SECTIONS, EXTRACT, VERIFY and WRITE."""

import asyncio
from typing import List

import httpx
import services.civicpatch_api as civicpatch_api
import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from runners.organizations_collector import sections
from runners.organizations_collector import verify as verify_rules
from runners.organizations_collector.role_asks import RoleAsk, role_asks
from runners.organizations_collector.schemas import (
    GoverningSectionsResponse,
    OrganizationsCollectorContext,
    OrganizationsCollectorState,
    OrganizationsCollectorStep,
    OtherOffice,
    OtherOfficesAnswer,
    RoleAnswer,
    RoleClaim,
)
from shared.schemas import PipelineRunLimits
from shared.utils.statuses import PipelineRunStatus
from utils import cost_utils
from utils.log_utils import PipelineRunLogger

Step = tuple[OrganizationsCollectorContext, OrganizationsCollectorState]
# Each question twice, the verified answers' union kept: one ask's answer varied run to run.
ASKS_PER_QUESTION = 2


async def start(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, OrganizationsCollectorStep.SELECT_SECTIONS


async def select_sections(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: OrganizationsCollectorContext, client: httpx.AsyncClient) -> Step:
    governing_law = context.data.config.governing_law
    if governing_law is None or not governing_law.source_page_ids:
        logger.info("no cached law to read")
        return context, OrganizationsCollectorStep.WRITE
    pages = [
        sections.GoverningLawPage.model_validate(
            await civicpatch_api.get_governing_law_source_page(client, context.data.jurisdiction_ocdid, page_id)
        )
        for page_id in governing_law.source_page_ids
    ]
    selected = [
        f"{sections.PAGE_KIND_TITLES[kind]}\n\n{await _selected_governing_law_text(context, logger, kind_pages)}"
        for kind, kind_pages in sections.pages_by_kind(pages, governing_law, context.data.config.jurisdiction_config.governing_law)
    ]
    config = context.data.config
    asks = role_asks(config.jurisdiction_config, config.name, config.government_form)
    logger.info(f"{len(asks)} roles to ask about")
    next_context = _next(context, governing_law_pages=pages, selected_governing_law_text="\n\n".join(selected), pending_asks=asks)
    return next_context, OrganizationsCollectorStep.EXTRACT


async def _selected_governing_law_text(context: OrganizationsCollectorContext, logger: PipelineRunLogger, pages: List[sections.GoverningLawPage]) -> str:
    """One kind's pages: all of them when they fit; else the sections picked from their headings,
    else those whose headings name the government; pages with no sections to pick from go whole."""
    whole = "\n\n".join(page.text for page in pages)
    found = sections.split_sections(pages)
    if sections.fits_whole(whole) or not found:
        return whole
    chosen = sections.picked(found, await _pick(context, found)) or sections.keyword_sections(found)
    logger.info(f"{len(whole):,} chars in {len(found)} sections: reading {len(chosen)}")
    return sections.joined(chosen) if chosen else whole


async def _pick(context: OrganizationsCollectorContext, found: List[sections.Section]) -> List[str]:
    response = await open_router_llm.run_prompt(
        context.pipeline_run_id,
        context.data.jurisdiction_ocdid,
        open_router_prompts.governing_sections_prompt(),
        prompt_name="governing_sections",
        response_schema=GoverningSectionsResponse,
        content=sections.heading_listing(found),
    )
    return GoverningSectionsResponse.model_validate(response).sections


def _next(context: OrganizationsCollectorContext, **data_updates) -> OrganizationsCollectorContext:
    return context.model_copy(update={"data": context.data.model_copy(update=data_updates)})


async def extract(limits: PipelineRunLimits, logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    """Every pending question, each `ASKS_PER_QUESTION` times; on the first pass, the offices
    nobody asked about as well. Stops before asking once the run's cap is spent."""
    if cost_utils.total_cost(context.pipeline_run_id) >= limits.pipeline_run_cap_usd:
        logger.warning(f"cost cap reached with {len(context.data.pending_asks)} roles unasked")
        return _next(context, pending_asks=[], stopped_at_cost_cap=True), OrganizationsCollectorStep.VERIFY
    asked = [ask for ask in context.data.pending_asks for _ in range(ASKS_PER_QUESTION)]
    first_pass = not context.data.claims
    answers = await asyncio.gather(*[_answer(context, logger, ask) for ask in asked])
    claims = [RoleClaim(ask=ask, answer=answer) for ask, answer in zip(asked, answers) if answer is not None]
    others = await _other_offices(context) if first_pass else context.data.other_offices
    return _next(context, claims=[*context.data.claims, *claims], pending_asks=[], other_offices=others), OrganizationsCollectorStep.VERIFY


async def _answer(context: OrganizationsCollectorContext, logger: PipelineRunLogger, ask: RoleAsk) -> RoleAnswer | None:
    """None when the question still failed after `run_prompt`'s retries: the role goes unanswered
    and VERIFY asks it again, rather than one role's failure ending the run."""
    question = open_router_prompts.governing_role_question(ask.role_label, ask.organization_name)
    try:
        response = await _ask(context, "governing_role", question, RoleAnswer)
    except Exception as error:
        logger.warning(f"{ask.role_id} in {ask.organization_name} unanswered: {type(error).__name__}: {error}")
        return None
    return RoleAnswer.model_validate(response)


async def _other_offices(context: OrganizationsCollectorContext) -> List[OtherOffice]:
    asked_labels = list(dict.fromkeys(ask.role_label for ask in context.data.pending_asks))
    question = open_router_prompts.governing_other_offices_question(asked_labels)
    response = await _ask(context, "governing_other_offices", question, OtherOfficesAnswer)
    return OtherOfficesAnswer.model_validate(response).offices


async def _ask(context: OrganizationsCollectorContext, prompt_name: str, question: str, response_schema):
    """The law first, the question last, so every question shares the cached law as its prefix."""
    law = context.data.selected_governing_law_text
    assert law is not None, "SELECT_SECTIONS always leaves the law for EXTRACT"
    return await open_router_llm.run_prompt(
        context.pipeline_run_id,
        context.data.jurisdiction_ocdid,
        open_router_prompts.governing_law_reader_prompt(),
        prompt_name=prompt_name,
        response_schema=response_schema,
        content=f"{law}\n\n{question}",
    )


async def verify(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    """Decides every role from all its answers so far; those with none verified go back to
    EXTRACT, unless the cap already stopped it."""
    governing_law = context.data.config.governing_law
    assert governing_law is not None, "SELECT_SECTIONS goes straight to WRITE when there is no law"
    outcomes = verify_rules.role_outcomes(
        context.data.claims,
        context.data.governing_law_pages,
        governing_law,
        context.data.config.jurisdiction_config.governing_law,
        ASKS_PER_QUESTION,
    )
    logger.info(
        f"{len(outcomes.verified)} verified, {len(outcomes.not_established)} not established,"
        f" {len(outcomes.conflicted)} in conflict, {len(outcomes.re_ask)} to ask again, {len(outcomes.unverified)} unverified"
    )
    if outcomes.re_ask and not context.data.stopped_at_cost_cap:
        return _next(context, outcomes=outcomes, pending_asks=outcomes.re_ask), OrganizationsCollectorStep.EXTRACT
    return _next(context, outcomes=outcomes), OrganizationsCollectorStep.WRITE


async def write(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, PipelineRunStatus.SUCCESS


async def send_error(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, PipelineRunStatus.ERROR


TRANSITION_MAP = {
    PipelineRunStatus.INIT: start,
    OrganizationsCollectorStep.SELECT_SECTIONS: select_sections,
    OrganizationsCollectorStep.EXTRACT: extract,
    OrganizationsCollectorStep.VERIFY: verify,
    OrganizationsCollectorStep.WRITE: write,
    PipelineRunStatus.SEND_ERROR: send_error,
}
