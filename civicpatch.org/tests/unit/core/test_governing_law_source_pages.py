import pytest

from core.governing_law_source_pages import cache_path, carries_html, page_hash

pytestmark = pytest.mark.unit

_TEXT = "# Chapter 3: City of Burlington\n\n§ 1. Corporate existence retained.\n"


def test_the_same_text_has_the_same_key_wherever_it_was_collected():
    assert cache_path(page_hash(_TEXT)) == cache_path(page_hash(_TEXT))
    assert cache_path(page_hash(_TEXT)) != cache_path(page_hash(_TEXT + " "))
    assert cache_path(page_hash(_TEXT)).startswith("governing_law/")
    assert cache_path(page_hash(_TEXT)).endswith(".md")


def test_markdown_passes_and_a_page_does_not():
    assert not carries_html(_TEXT)
    assert not carries_html("**bold** and [a link](/statutes/title/24APPENDIX) and 3 < 5 > 2")
    assert carries_html("<div class='x'>§ 1.</div>")
    assert carries_html("text</p>")
    assert carries_html("<br>")
