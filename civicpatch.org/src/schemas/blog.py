import datetime

from pydantic import BaseModel


class BlogIndexEntry(BaseModel):
    slug: str
    title: str
    date: datetime.date
    description: str
    author: str


class BlogPost(BaseModel):
    slug: str
    title: str
    date: datetime.date
    description: str
    author: str
    draft: bool
    updated_at: datetime.date | None
    content_html: str
    toc_html: str
