from typing import List, Optional

from pydantic import BaseModel


class OdSyncRequestSchema(BaseModel):
    jurisdiction_ocdids: Optional[List[str]] = None
