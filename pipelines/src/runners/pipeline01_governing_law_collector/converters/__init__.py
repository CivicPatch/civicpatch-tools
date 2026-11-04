"""Turning a fetched page into markdown, chosen by content type. Only markdown leaves the process."""

from ..schemas import FetchedPage
from . import html, pdf

# Shorter than this after conversion, a page is a shell: script-rendered, or a frameset.
MIN_MARKDOWN_CHARS = 200
# Some hosts serve a PDF as octet-stream; the file says what it is.
PDF_MAGIC = b"%PDF-"


class UnsupportedContentType(Exception):
    pass


def to_markdown(page: FetchedPage) -> str:
    if "html" in page.content_type:
        return html.to_markdown(page.body)
    if "pdf" in page.content_type or page.body.startswith(PDF_MAGIC):
        try:
            return pdf.to_markdown(page.body)
        except pdf.UnreadablePdf as unreadable:
            raise UnsupportedContentType(f"{page.url}: not a readable PDF ({unreadable})") from unreadable
    raise UnsupportedContentType(f"{page.url}: no converter for {page.content_type!r}")


def is_nearly_empty(markdown: str) -> bool:
    return len(markdown.strip()) < MIN_MARKDOWN_CHARS
