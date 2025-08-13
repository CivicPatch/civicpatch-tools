import pytest
from steps.step_04_preprocess_page_content.filter_content import filter_content
from bs4 import BeautifulSoup

def get_divisions_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    return [
        el.get_text() or ""
        for el in soup.find_all()
        if el.get_text() and (
            "ward" in el.get_text() or
            "at-large" in el.get_text() or
            "district" in el.get_text() or
            "citywide" in el.get_text()
        )
    ]

def test_filter_content_preserves_division_ward():
    html = "<div>Jane Doe represents ward 5.</div><div>Unrelated text.</div>"
    filtered = filter_content(html)
    divisions = get_divisions_from_html(filtered)
    assert any("ward" in d for d in divisions)

def test_filter_content_preserves_division_at_large():
    html = "<div>John Smith is an at-large council member.</div>"
    filtered = filter_content(html)
    divisions = get_divisions_from_html(filtered)
    assert any("at-large" in d for d in divisions)

def test_filter_content_preserves_division_alias():
    html = "<div>He serves citywide.</div>"
    filtered = filter_content(html)
    divisions = get_divisions_from_html(filtered)
    assert any("citywide" in d for d in divisions) or any("at-large" in d for d in divisions)

def test_filter_content_removes_irrelevant():
    html = "<div>Unrelated text.</div>"
    filtered = filter_content(html)
    soup = BeautifulSoup(filtered, "html.parser")
    # Should not contain any division keywords
    text = soup.get_text() or ""
    # Defensive: ensure text is a string
    assert isinstance(text, str)
    assert not any(
        kw in text for kw in ["ward", "at-large", "district", "citywide"]
    )