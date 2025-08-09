from pydantic import BaseModel
from typing import List, Optional

class OpenAIDataPoint(BaseModel):
    data: Optional[str] = None
    llm_confidence: float
    llm_confidence_reason: str

class OpenAIPerson(BaseModel):
    name: str
    roles: List[OpenAIDataPoint]
    divisions: List[OpenAIDataPoint]
    phone_number: OpenAIDataPoint
    email: OpenAIDataPoint
    website: OpenAIDataPoint
    start_date: OpenAIDataPoint
    end_date: OpenAIDataPoint

class OpenAIPeopleArray(BaseModel):
    people: List[OpenAIPerson]
    thought: Optional[str] = None