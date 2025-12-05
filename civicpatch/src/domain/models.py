from pydantic import BaseModel
from typing import List, Optional

class Person(BaseModel):
    name: str
    roles: List[str]
    divisions: List[str]
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None

    jurisdiction_id: str
    cdn_image: Optional[str] = None
    sources: List[str]  # List of source URLs where information was found
    updated_at: str