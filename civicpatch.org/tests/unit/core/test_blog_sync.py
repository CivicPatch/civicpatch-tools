from datetime import datetime, timezone

import pytest

from services.blog_sync import (
    compute_slug,
    discussion_to_post,
    is_draft,
    parse_post_body,
    render_post_html,
    sanitize_html,
)
from schemas.blog import BodyFrontmatter
from schemas.webhooks.blog_sync import DiscussionPayload


def _make_discussion(
    number: int = 42,
    title: str = "Test Post",
    body: str = "---\nslug: test\ndescription: hi\n---\nHello",
    labels: list[str] | None = None,
    author_login: str = "testuser",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    url: str = "https://github.com/x/y/discussions/42",
) -> DiscussionPayload:
    return DiscussionPayload(
        number=number,
        title=title,
        body=body,
        created_at=created_at or datetime(2026, 5, 14, tzinfo=timezone.utc),
        updated_at=updated_at or datetime(2026, 5, 14, tzinfo=timezone.utc),
        author_login=author_login,
        labels=labels or [],
        url=url,
    )


@pytest.mark.unit
def test_parse_post_body_with_frontmatter():
    raw = "---\nslug: volunteer\ndescription: Help\n---\n\n## Body"
    fm, body = parse_post_body(raw)
    assert fm is not None
    assert fm.slug == "volunteer"
    assert fm.description == "Help"
    assert "## Body" in body


@pytest.mark.unit
def test_parse_post_body_without_frontmatter():
    raw = "## Just a heading\n\nNo frontmatter here."
    fm, body = parse_post_body(raw)
    assert fm is None
    assert body == raw


@pytest.mark.unit
def test_parse_post_body_with_malformed_yaml():
    raw = "---\nslug: : : invalid\n---\nbody"
    fm, body = parse_post_body(raw)
    assert fm is None


@pytest.mark.unit
def test_render_post_html_includes_toc_for_headings():
    content, toc = render_post_html("## Section One\n\nBody\n\n## Section Two")
    assert "Section One" in toc
    assert "Section Two" in toc


@pytest.mark.unit
def test_render_post_html_empty_toc_when_no_headings():
    content, toc = render_post_html("Just a paragraph.")
    assert toc == ""


@pytest.mark.unit
def test_render_post_html_renders_fenced_code_and_strikethrough():
    md = "```python\nprint('hi')\n```\n\n~~strike~~"
    content, _ = render_post_html(md)
    assert "<code" in content
    assert "<del>strike</del>" in content


@pytest.mark.unit
def test_sanitize_html_strips_script_but_keeps_tables():
    html = "<script>alert(1)</script><table><tr><td>cell</td></tr></table>"
    result = sanitize_html(html)
    assert "<script>" not in result
    assert "<table>" in result
    assert "<td>cell</td>" in result


@pytest.mark.unit
def test_sanitize_html_preserves_code_class_for_highlighting():
    html = '<pre><code class="language-python">x</code></pre>'
    result = sanitize_html(html)
    assert 'class="language-python"' in result


@pytest.mark.unit
def test_sanitize_html_preserves_heading_ids_for_toc_anchors():
    html = '<h2 id="section-one">Section</h2><h3 id="sub">Sub</h3>'
    result = sanitize_html(html)
    assert 'id="section-one"' in result
    assert 'id="sub"' in result


@pytest.mark.unit
def test_compute_slug_uses_frontmatter_when_set():
    fm = BodyFrontmatter(slug="volunteer")
    d = _make_discussion(number=42, title="How to Contribute")
    assert compute_slug(fm, d) == "volunteer"


@pytest.mark.unit
def test_compute_slug_falls_back_to_number_kebab_title():
    fm = BodyFrontmatter()
    d = _make_discussion(number=42, title="How to Contribute!")
    assert compute_slug(fm, d) == "42-how-to-contribute"


@pytest.mark.unit
def test_is_draft_true_when_draft_label_present():
    d = _make_discussion(labels=["draft"])
    assert is_draft(d) is True


@pytest.mark.unit
def test_is_draft_false_when_no_draft_label():
    d = _make_discussion(labels=["other"])
    assert is_draft(d) is False


@pytest.mark.unit
def test_discussion_to_post_happy_path():
    d = _make_discussion(
        number=42,
        title="Hello World",
        body="---\nslug: hello\ndescription: greet\nauthor: brand\n---\n\n## H1\n\nbody",
        author_login="shelltr",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        url="https://example.com/42",
    )
    post = discussion_to_post(d)
    assert post is not None
    assert post.slug == "hello"
    assert post.title == "Hello World"
    assert post.description == "greet"
    assert post.author == "brand"
    assert post.date.isoformat() == "2026-01-01"
    assert post.updated_at is not None and post.updated_at.isoformat() == "2026-02-01"
    assert post.discussion_url == "https://example.com/42"
    assert post.draft is False
    assert "H1" in post.toc_html


@pytest.mark.unit
def test_discussion_to_post_description_falls_back_to_first_paragraph():
    body = "---\nslug: x\n---\n\nThis is the first paragraph.\n\nSecond paragraph."
    d = _make_discussion(body=body)
    post = discussion_to_post(d)
    assert post is not None
    assert post.description == "This is the first paragraph."


@pytest.mark.unit
def test_discussion_to_post_author_falls_back_to_discussion_author():
    body = "---\nslug: x\n---\n\nbody"
    d = _make_discussion(body=body, author_login="shelltr")
    post = discussion_to_post(d)
    assert post is not None
    assert post.author == "shelltr"


@pytest.mark.unit
def test_discussion_to_post_returns_none_when_no_frontmatter():
    d = _make_discussion(body="just a body, no frontmatter")
    assert discussion_to_post(d) is None
