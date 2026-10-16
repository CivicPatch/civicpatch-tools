import re
from typing import List, Optional

from runners.people_collector.schemas import RelevantPageResponseSchema
from shared.schemas import PublishedSourcePage
from shared.utils.content_hash import content_hash
from shared.utils.url_utils import canonical_url

# Embedded maps load their tiles in a different order on every fetch, which changed the hash of
# pages whose text had not changed.
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def page_content_hash(markdown: str) -> str:
    """The page's text, images left out: only text changes mean a fresh reading."""
    return content_hash(_MARKDOWN_IMAGE.sub("", markdown))


def published_source_page(
    published_source_pages: List[PublishedSourcePage], page_url: str
) -> Optional[PublishedSourcePage]:
    """This page's latest published `source_pages` row, if it has one."""
    key = canonical_url(page_url)
    for source_page in published_source_pages:
        if canonical_url(source_page.source_url) == key:
            return source_page
    return None


def is_unchanged(source_page: PublishedSourcePage, page_hash: str, prompt_hash: str) -> bool:
    """Whether the LLM would see exactly what it saw last time: the same text and the same
    prompts. Anything else is read fresh."""
    if source_page.is_relevant is None:
        return False
    return source_page.page_hash == page_hash and source_page.prompt_hash == prompt_hash


def source_page_relevance(source_page: PublishedSourcePage) -> RelevantPageResponseSchema:
    """The row's answer in the shape a fresh one arrives in, so both take the same path."""
    return RelevantPageResponseSchema(
        is_relevant=bool(source_page.is_relevant), relevant_urls=source_page.relevant_urls or []
    )
