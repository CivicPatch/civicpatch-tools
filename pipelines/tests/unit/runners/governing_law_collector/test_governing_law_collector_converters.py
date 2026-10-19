"""Pages to markdown: real statute text (public domain) inside made-up site chrome, so every
section must survive and the chrome must not. No HTML out."""

import re
from pathlib import Path

import pytest

from runners.governing_law_collector.converters import UnsupportedContentType, is_thin, to_markdown
from runners.governing_law_collector.schemas import FetchedPage

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"
_HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(\s[^<>]*)?>")


def _page(name: str, content_type: str = "text/html; charset=utf-8") -> FetchedPage:
    return FetchedPage(url=f"https://example.gov/{name}", content_type=content_type, body=(FIXTURES / name).read_bytes(), by_browser=False)


def test_a_vermont_chapter_keeps_every_section_and_no_markup():
    markdown = to_markdown(_page("vt_24_vsa_chapter_39.html"))

    assert len(set(re.findall(r"§ (13\d\d)\.", markdown))) == 21
    assert "a presiding officer, a clerk, five trustees" in markdown
    assert not _HTML_TAG.search(markdown)
    assert not is_thin(markdown)


def test_a_short_statute_is_kept_whole_and_its_site_chrome_dropped():
    """MCL 61.1 is one sentence; the page around it is navigation and a footer."""
    markdown = to_markdown(_page("mi_mcl_61_1.html"))

    assert "This act is the charter for all villages incorporated under this act." in markdown
    assert "Acceptable Use Policy" not in markdown
    assert not _HTML_TAG.search(markdown)


def test_a_script_rendered_shell_is_thin():
    shell = FetchedPage(
        url="https://example.gov/app", content_type="text/html",
        body=b"<html><head><script src='app.js'></script></head><body><div id='root'></div></body></html>",
        by_browser=False,
    )

    assert is_thin(to_markdown(shell))


def test_a_pdf_has_no_converter_yet():
    with pytest.raises(UnsupportedContentType):
        to_markdown(FetchedPage(url="https://example.gov/c.pdf", content_type="application/pdf", body=b"%PDF-1.7", by_browser=False))


def test_a_tag_trafilatura_leaves_is_dropped_and_its_words_kept():
    """Barre town's charter underlines its notes; the converter used to pass <u> through."""
    underlined = FetchedPage(
        url="https://example.gov/charter", content_type="text/html",
        body=("<html><body><article><p>" + "§ 101. Corporate existence retained. " * 10
              + "(Amended 2023, No. M-3.) <u>Notes</u> History.</p></article></body></html>").encode(),
        by_browser=False,
    )

    markdown = to_markdown(underlined)

    assert "Notes" in markdown
    assert not _HTML_TAG.search(markdown)
