import trafilatura


def to_markdown(body: bytes) -> str:
    """The page's content as markdown: navigation and footers dropped, headings, tables and
    in-content links kept. Compared on six legal pages (2026-10-18): every section kept."""
    return trafilatura.extract(
        body,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        include_formatting=True,
        favor_recall=True,
    ) or ""
