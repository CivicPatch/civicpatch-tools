import datetime

from pydantic import BaseModel


class Election(BaseModel):
    date: datetime.date
    state: str
    title: str
    note: str | None = None
