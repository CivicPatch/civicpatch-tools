from typing import List

from pydantic import BaseModel


class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]
