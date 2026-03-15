from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Person(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    jurisdiction_ocdid: str


class JobConfig(BaseModel):
    max_pages: int
    pipeline_run_cost_limit: Decimal  # in USD


class JurisdictionId(BaseModel):
    country: str
    state: str
    county: Optional[str] = None
    place_label: str = "place"
    place: str
    jurisdiction_type: str
    output_type: str
