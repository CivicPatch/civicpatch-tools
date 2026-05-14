import pytest

from lib.blog import _parse_post


@pytest.mark.unit
def test_parse_post_includes_toc_html_for_post_with_headings(tmp_path):
    post_file = tmp_path / "2026-01-01-test-post.md"
    post_file.write_text(
        "---\ntitle: Test\ndate: 2026-01-01\n---\n"
        "## Section One\n\nSome content.\n\n"
        "## Section Two\n\nMore content.\n"
    )
    result = _parse_post(post_file)
    assert result is not None
    assert "Section One" in result.toc_html
    assert "Section Two" in result.toc_html


@pytest.mark.unit
def test_parse_post_toc_html_empty_when_no_headings(tmp_path):
    post_file = tmp_path / "2026-01-01-test-post.md"
    post_file.write_text(
        "---\ntitle: Test\ndate: 2026-01-01\n---\n"
        "Just some content with no headings.\n"
    )
    result = _parse_post(post_file)
    assert result is not None
    assert result.toc_html == ""


@pytest.mark.unit
def test_parse_post_content_html_still_rendered(tmp_path):
    post_file = tmp_path / "2026-01-01-test-post.md"
    post_file.write_text(
        "---\ntitle: Test\ndate: 2026-01-01\n---\n"
        "## Intro\n\nHello **world**.\n"
    )
    result = _parse_post(post_file)
    assert result is not None
    assert "<strong>world</strong>" in result.content_html
