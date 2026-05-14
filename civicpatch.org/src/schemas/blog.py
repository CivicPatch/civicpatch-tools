import datetime

from pydantic import BaseModel


class BodyFrontmatter(BaseModel):
    slug: str | None = None
    description: str | None = None
    author: str | None = None


class BlogIndexEntry(BaseModel):
    slug: str
    title: str
    date: datetime.date
    description: str
    author: str


class BlogPost(BlogIndexEntry):
    draft: bool
    updated_at: datetime.date | None
    content_html: str
    toc_html: str
    discussion_url: str | None = None
