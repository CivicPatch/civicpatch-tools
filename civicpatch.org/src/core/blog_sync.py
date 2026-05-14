import re

import bleach
import frontmatter
import markdown as md_lib
from pydantic import ValidationError

from schemas.blog import BlogPost, BodyFrontmatter
from schemas.webhooks.blog_sync import DiscussionPayload

_ALLOWED_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote",
    "em", "strong", "del", "s",
    "code", "pre", "hr", "br",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "input",
]
_ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    "pre": ["class"],
    "th": ["align"],
    "td": ["align"],
    "input": ["type", "checked", "disabled"],
}

_KEBAB_RE = re.compile(r"[^a-z0-9]+")


def parse_post_body(raw: str) -> tuple[BodyFrontmatter | None, str]:
    try:
        post = frontmatter.loads(raw)
    except Exception:
        return None, raw
    if not post.metadata:
        return None, raw
    try:
        return BodyFrontmatter.model_validate(post.metadata), post.content
    except ValidationError:
        return None, raw


def render_post_html(md_body: str) -> tuple[str, str]:
    md = md_lib.Markdown(
        extensions=["tables", "toc", "fenced_code", "pymdownx.tilde"],
        extension_configs={"toc": {"toc_depth": 2}},
    )
    content_html = md.convert(md_body)
    toc = getattr(md, "toc", "")
    return content_html, toc if "<li>" in toc else ""


def sanitize_html(html: str) -> str:
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=False)


def _title_to_kebab(title: str) -> str:
    return _KEBAB_RE.sub("-", title.lower()).strip("-")


def compute_slug(fm: BodyFrontmatter, discussion: DiscussionPayload) -> str:
    if fm.slug:
        return fm.slug
    return f"{discussion.number}-{_title_to_kebab(discussion.title)}"


def is_draft(discussion: DiscussionPayload) -> bool:
    return "draft" in discussion.labels


def _first_paragraph(md_body: str) -> str:
    for chunk in md_body.split("\n\n"):
        text = chunk.strip()
        if text and not text.startswith("#"):
            return text
    return ""


def discussion_to_post(discussion: DiscussionPayload) -> BlogPost | None:
    body_fm, md_body = parse_post_body(discussion.body)
    if body_fm is None:
        return None
    content_html_raw, toc_html = render_post_html(md_body)
    content_html = sanitize_html(content_html_raw)
    description = body_fm.description or _first_paragraph(md_body)
    author = body_fm.author or discussion.author_login
    return BlogPost(
        slug=compute_slug(body_fm, discussion),
        title=discussion.title,
        date=discussion.created_at.date(),
        description=description,
        author=author,
        draft=False,
        updated_at=discussion.updated_at.date(),
        content_html=content_html,
        toc_html=toc_html,
        discussion_url=discussion.url,
    )
