from decimal import Decimal
from enum import StrEnum
from typing import List, Optional

from domain.pipeline_run_context import PipelineRunContext
from pydantic import BaseModel, Field
from runners.organizations_collector.role_asks import RoleAsk
from runners.organizations_collector.sections import GoverningLawPage
from shared.schemas import GovernmentForm, GoverningLaw, GoverningLawKind, GoverningLawOrganizations, SelectionMethod
from shared.utils.layered_config import MergedConfig
from shared.utils.statuses import PipelineRunStatus


class OrganizationsCollectorStep(StrEnum):
    """The organizations_collector's own steps; the lifecycle every pipeline shares is `PipelineRunStatus`."""

    SELECT_SECTIONS = "SELECT_SECTIONS"
    EXTRACT = "EXTRACT"
    VERIFY = "VERIFY"
    WRITE = "WRITE"


OrganizationsCollectorState = PipelineRunStatus | OrganizationsCollectorStep


class OrganizationsCollectorConfig(BaseModel):
    name: str
    # The most one organizations_collector run may spend, from its collector_settings row. The
    # engine reads this name off every pipeline's config; None inherits `pipeline.yml`'s default.
    pipeline_run_cap_usd: Optional[Decimal] = None
    # The jurisdiction's `extras_governing_law`: which cached texts to read. None before plan 1's run.
    governing_law: Optional[GoverningLaw]
    # The country's files merged with the state's: its roles, its forms' organizations, and its
    # governing law block, whose classifications list which cached pages are statute.
    jurisdiction_config: MergedConfig
    # The jurisdiction's `extras_government_form`; None asks about every form its name allows.
    government_form: Optional[GovernmentForm]


class GoverningSectionsResponse(BaseModel):
    sections: List[str]


class FilledBy(StrEnum):
    """How the law says an office is filled, or that it does not say."""

    ELECTED_BY_VOTERS = "elected_by_voters"
    ELECTED_BY_MEMBERS = "elected_by_members"
    APPOINTED = "appointed"
    NOT_STATED = "not_stated"


class RoleAnswer(BaseModel):
    established: bool
    # The office's name as the law writes it ("Selectboard member"); "" when not established.
    label: str
    filled_by: FilledBy
    # None when the law states no number.
    maximum_memberships: Optional[int]
    # Short and exact: it locates the clause, and VERIFY widens it to what supports the claim.
    quote: str


class RoleClaim(BaseModel):
    ask: RoleAsk
    answer: RoleAnswer


class OtherOffice(BaseModel):
    label: str
    filled_by: FilledBy
    quote: str


class OtherOfficesAnswer(BaseModel):
    offices: List[OtherOffice]


class VerifiedRole(BaseModel):
    ask: RoleAsk
    # The office's name as the law writes it.
    label: str
    # None: the law establishes the office without saying how it is filled.
    selection_method: Optional[SelectionMethod]
    maximum_memberships: Optional[int]
    # The verifier's quote: the sentence, section body or section that supports the claim.
    quote: str
    source_page_id: str
    source_url: str
    page_kind: GoverningLawKind


class RoleOutcomes(BaseModel):
    verified: List[VerifiedRole] = []
    not_established: List[RoleAsk] = []
    # Verified answers that disagree on how the office is filled, with no charter answer to settle it.
    conflicted: List[RoleAsk] = []
    # No answer verified yet: asked again, up to `verify.MAX_ROUNDS` rounds.
    re_ask: List[RoleAsk] = []
    # No answer verified in `verify.MAX_ROUNDS` rounds.
    unverified: List[RoleAsk] = []


class OrganizationsCollectorData(BaseModel):
    jurisdiction_ocdid: str
    config: OrganizationsCollectorConfig
    # The cached pages, whole: what VERIFY checks quotes against. Never saved.
    governing_law_pages: List[GoverningLawPage] = Field(default=[], exclude=True)
    # What EXTRACT reads: the whole law, or the sections picked from it. Never saved.
    selected_governing_law_text: Optional[str] = Field(default=None, exclude=True)
    # The questions EXTRACT still has to ask: every role at first, then those VERIFY sends back.
    pending_asks: List[RoleAsk] = []
    claims: List[RoleClaim] = []
    other_offices: List[OtherOffice] = []
    # The run's cap was reached before every question was asked; WRITE reports it.
    stopped_at_cost_cap: bool = False
    # VERIFY's latest decision on every role asked.
    outcomes: Optional[RoleOutcomes] = None
    organizations: Optional[GoverningLawOrganizations] = None


class OrganizationsCollectorContext(PipelineRunContext[OrganizationsCollectorData, OrganizationsCollectorState]):
    pass
