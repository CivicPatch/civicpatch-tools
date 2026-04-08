from pydantic import BaseModel
from typing import List, Optional, Tuple
from enum import Enum
from shared.utils.config_utils import get_designations
from shared.schemas import Office, Official

class Person(BaseModel):
    name: str
    # address: NOTE: not implemented, we are NOT collecting addresses
    other_names: List[str] = []
    roles: List[str] = []
    designations: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None

    jurisdiction_ocdid: str 
    cdn_image: Optional[str] = None
    source_urls: List[str] 
    updated_at: str
