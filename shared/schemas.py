from pydantic import BaseModel, computed_field
from typing import Optional
from decimal import Decimal


class ProcessConfig(BaseModel):
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
    
    @computed_field
    @property
    def partial_file_path(self) -> str:
        """
        Converts jurisdiction components to a reversible, human-friendly folder path.
        Example: "il/local/county_dupage__place_naperville__government"
        """
        file_path = f"{self.state}/{self.output_type}/"
        if self.county:
            file_path += f"county_{self.county}__"
        file_path += f"{self.place_label}_{self.place}__{self.jurisdiction_type}.yml"
        
        return file_path