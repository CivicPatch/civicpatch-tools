import re

import trafilatura

# Trafilatura keeps some inline formatting as literal tags: Barre town's charter has <u>Notes</u>.
_LEFTOVER_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(\s[^<>]*)?>")


def to_markdown(body: bytes) -> str:
    """The page's content as markdown: navigation and footers dropped, headings, tables and
    in-content links kept, any leftover tag dropped with its words kept. Compared on six legal
    pages (2026-10-18): every section kept."""
    markdown = trafilatura.extract(
        body,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        include_formatting=True,
        favor_recall=True,
    ) or ""
    return _LEFTOVER_TAG.sub("", markdown)