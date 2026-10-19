from pydantic import BaseModel


class GoverningLawSourcePageRequest(BaseModel):
    source_url: str
    text: str


class GoverningLawSourcePageReuseRequest(BaseModel):
    source_url: str
