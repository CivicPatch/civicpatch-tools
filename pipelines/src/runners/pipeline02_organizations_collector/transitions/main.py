"""One handler per state of ORGANIZATIONS_COLLECTOR_TRANSITIONS. Each takes the context and
answers it with the next state; the engine checks the answer against the graph."""

import asyncio
from typing import List

import httpx
import services.civicpatch_api as civicpatch_api
import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from runners.pipeline02_organizations_collector import sections
from runners.pipeline02_organizations_collector import verify as verify_rules
from ..role_asks import RoleAsk, presiding_asks, role_asks
from ..schemas import (
    FilledBy,
    GoverningSectionsResponse,
    OrganizationsCollectorContext,
    OrganizationsCollectorState,
    OrganizationsCollectorStep,
    PresidingAnswer,
    PresidingOffice,
    RoleAnswer,
    RoleClaim,
)
from shared.schemas import GoverningLawOrganizations, GoverningLawOrganizationsExtras, JurisdictionExtras, PipelineRunLimits
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
    presiding = presiding_asks(config.jurisdiction_config, config.name, config.government_form)
    logger.info(f"{len(asks)} roles to ask about, {len(presiding)} presiding candidates in one question")
    next_context = _next(
        context, governing_law_pages=pages, selected_governing_law_text="\n\n".join(selected), pending_asks=asks, presiding_asks=presiding
    )
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
    """Every pending question, each `ASKS_PER_QUESTION` times; on the first pass, the presiding
    candidates as well. Stops before asking once the run's cap is spent."""
    if cost_utils.total_cost(context.pipeline_run_id) >= limits.pipeline_run_cap_usd:
        logger.warning(f"cost cap reached with {len(context.data.pending_asks)} roles unasked")
        return _next(context, pending_asks=[], stopped_at_cost_cap=True), OrganizationsCollectorStep.VERIFY
    asked = [ask for ask in context.data.pending_asks for _ in range(ASKS_PER_QUESTION)]
    first_pass = not context.data.claims
    answers = await asyncio.gather(*[_answer(context, logger, ask) for ask in asked])
    claims = [RoleClaim(ask=ask, answer=answer) for ask, answer in zip(asked, answers) if answer is not None]
    presiding = await _presiding(context, logger) if first_pass else []
    all_claims = [*context.data.claims, *claims, *presiding]
    return _next(context, claims=all_claims, pending_asks=[]), OrganizationsCollectorStep.VERIFY


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


async def _presiding(context: OrganizationsCollectorContext, logger: PipelineRunLogger) -> List[RoleClaim]:
    """Each ask of the one question answers every candidate: an office it returns, or one it
    leaves out, which is not established. An ask that failed after retries answers none."""
    asks = context.data.presiding_asks
    if not asks:
        return []
    organization_name = asks[0].organization_name
    question = open_router_prompts.governing_presiding_question(organization_name, [(ask.role_id, ask.names) for ask in asks])
    responses = await asyncio.gather(
        *[_ask(context, "governing_presiding", question, PresidingAnswer) for _ in range(ASKS_PER_QUESTION)], return_exceptions=True
    )
    claims: List[RoleClaim] = []
    for response in responses:
        if isinstance(response, BaseException):
            logger.warning(f"presiding candidates in {organization_name} unanswered: {type(response).__name__}: {response}")
            continue
        claims = [*claims, *presiding_claims(asks, PresidingAnswer.model_validate(response))]
    return claims


def presiding_claims(asks: List[RoleAsk], answer: PresidingAnswer) -> List[RoleClaim]:
    offices = {office.role_id: office for office in answer.offices}
    return [RoleClaim(ask=ask, answer=_presiding_answer(offices.get(ask.role_id))) for ask in asks]


def _presiding_answer(office: PresidingOffice | None) -> RoleAnswer:
    if office is None:
        return RoleAnswer(established=False, label="", filled_by=FilledBy.NOT_STATED, maximum_memberships=None, quote="")
    return RoleAnswer(
        established=True, label=office.label, filled_by=office.filled_by, maximum_memberships=office.maximum_memberships, quote=office.quote
    )


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
    """Decides every role from all its answers so far; those with no quote yet go back to
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
    asked = {claim.ask.role_id for claim in context.data.claims}
    logger.info(f"{len(outcomes.posts)} of {len(asked)} roles quoted from the law, {len(outcomes.re_ask)} to ask again")
    if outcomes.re_ask and not context.data.stopped_at_cost_cap:
        return _next(context, outcomes=outcomes, pending_asks=outcomes.re_ask), OrganizationsCollectorStep.EXTRACT
    return _next(context, outcomes=outcomes), OrganizationsCollectorStep.WRITE


async def write(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: OrganizationsCollectorContext, client: httpx.AsyncClient) -> Step:
    """No law read, nothing written: an empty list would claim the law establishes no posts."""
    outcomes = context.data.outcomes
    governing_law = context.data.config.governing_law
    if outcomes is None or governing_law is None:
        logger.info("no law was read, so nothing is written")
        return context, PipelineRunStatus.SUCCESS
    if context.data.stopped_at_cost_cap:
        logger.warning(f"cost cap reached: writing {len(outcomes.posts)} posts, some roles unasked")
    organizations = GoverningLawOrganizations(
        posts=outcomes.posts,
        extras=GoverningLawOrganizationsExtras(governing_law_collected_at=governing_law.collected_at),
    )
    await civicpatch_api.patch_jurisdiction_extras(
        client, context.data.jurisdiction_ocdid, JurisdictionExtras(extras_organizations=organizations)
    )
    return _next(context, organizations=organizations), PipelineRunStatus.SUCCESS


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
