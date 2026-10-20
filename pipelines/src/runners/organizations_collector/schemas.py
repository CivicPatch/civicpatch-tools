from decimal import Decimal
from enum import StrEnum
from typing import List, Optional

from domain.pipeline_run_context import PipelineRunContext
from pydantic import BaseModel, Field
from shared.schemas import GoverningLaw, GoverningLawOrganizations
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


class OrganizationsCollectorData(BaseModel):
    jurisdiction_ocdid: str
    config: OrganizationsCollectorConfig
    # What EXTRACT reads: the whole law, or the sections picked from it. Never saved.
    selected_governing_law_text: Optional[str] = Field(default=None, exclude=True)
    organizations: Optional[GoverningLawOrganizations] = None


class OrganizationsCollectorContext(PipelineRunContext[OrganizationsCollectorData, OrganizationsCollectorState]):
    pass


class GoverningSectionsResponse(BaseModel):
    sections: List[str]
