"""Turning a fetched page into markdown, chosen by content type. Only markdown leaves the process."""

from ..schemas import FetchedPage
from . import html

# Shorter than this after conversion, a page is a shell: script-rendered, or a frameset.
MIN_MARKDOWN_CHARS = 200


class UnsupportedContentType(Exception):
    pass


def to_markdown(page: FetchedPage) -> str:
    if "html" in page.content_type:
        return html.to_markdown(page.body)
    raise UnsupportedContentType(f"{page.url}: no converter for {page.content_type!r}")


def is_thin(markdown: str) -> bool:
    return len(markdown.strip()) < MIN_MARKDOWN_CHARS
