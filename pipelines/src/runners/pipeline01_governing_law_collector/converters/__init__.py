"""Turning a fetched page into markdown, chosen by content type. Only markdown leaves the process."""

from ..schemas import FetchedPage
from . import ecode360, html, ocr, pdf

# Shorter than this after conversion, a page is a shell: script-rendered, or a frameset.
MIN_MARKDOWN_CHARS = 200
# Some hosts serve a PDF as octet-stream; the file says what it is.
PDF_MAGIC = b"%PDF-"


class UnsupportedContentType(Exception):
    pass


def to_markdown(page: FetchedPage) -> str:
    if ecode360.is_print_page(page.url):
        return ecode360.to_markdown(page.body)
    if "html" in page.content_type:
        return html.to_markdown(page.body)
    if is_pdf(page):
        try:
            text = pdf.to_markdown(page.body)
            # A scan carries no text layer: its pages are read instead.
            return ocr.to_markdown(page.body) if is_nearly_empty(text) else text
        except pdf.UnreadablePdf as unreadable:
            raise UnsupportedContentType(f"{page.url}: not a readable PDF ({unreadable})") from unreadable
    raise UnsupportedContentType(f"{page.url}: no converter for {page.content_type!r}")


def is_pdf(page: FetchedPage) -> bool:
    return "pdf" in page.content_type or page.body.startswith(PDF_MAGIC)


def is_nearly_empty(markdown: str) -> bool:
    return len(markdown.strip()) < MIN_MARKDOWN_CHARS
