from pydantic import BaseModel
from typing import Optional
from decimal import Decimal


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
