from datetime import datetime

from pydantic import BaseModel


class DiscussionPayload(BaseModel):
    number: int
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
    author_login: str
    labels: list[str]
    url: str


class BlogSyncPayload(BaseModel):
    discussions: list[DiscussionPayload]
