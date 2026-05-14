import json
import logging
import re

import bleach
import frontmatter
import markdown as md_lib
from pydantic import BaseModel, ValidationError

import lib.redis as redis_store
from schemas.blog import BlogIndexEntry, BlogPost, BodyFrontmatter
from schemas.webhooks.blog_sync import BlogSyncPayload, DiscussionPayload

logger = logging.getLogger(__name__)

INDEX_KEY = "blog:index"
POST_KEY_PREFIX = "blog:post:"

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


class SyncResult(BaseModel):
    synced: list[str]
    skipped: list[tuple[int, str]] = []


class SyncCollisionError(Exception):
    def __init__(self, slug: str, numbers: list[int]):
        super().__init__(f"slug '{slug}' claimed by discussions {numbers}")
        self.slug = slug
        self.numbers = numbers


def _to_index_entry(post: BlogPost) -> BlogIndexEntry:
    return BlogIndexEntry(
        slug=post.slug,
        title=post.title,
        date=post.date,
        description=post.description,
        author=post.author,
    )


async def _existing_post_slugs() -> set[str]:
    slugs: set[str] = set()
    async for key in redis_store.redis_client.scan_iter(match=f"{POST_KEY_PREFIX}*"):
        slugs.add(key.removeprefix(POST_KEY_PREFIX))
    return slugs


def _build_posts(payload: BlogSyncPayload) -> tuple[dict[str, BlogPost], list[tuple[int, str]]]:
    posts: dict[str, BlogPost] = {}
    skipped: list[tuple[int, str]] = []
    slug_owner: dict[str, int] = {}
    for d in payload.discussions:
        if is_draft(d):
            continue
        post = discussion_to_post(d)
        if post is None:
            logger.info("blog sync: skipping discussion #%d (no frontmatter)", d.number)
            skipped.append((d.number, "no frontmatter"))
            continue
        if post.slug in slug_owner:
            raise SyncCollisionError(post.slug, [slug_owner[post.slug], d.number])
        slug_owner[post.slug] = d.number
        posts[post.slug] = post
    return posts, skipped


def _serialize_index(posts: dict[str, BlogPost]) -> str:
    entries = sorted(
        [_to_index_entry(p) for p in posts.values()],
        key=lambda e: e.date,
        reverse=True,
    )
    return json.dumps([e.model_dump(mode="json") for e in entries])


async def sync_blog_posts(payload: BlogSyncPayload) -> SyncResult:
    posts, skipped = _build_posts(payload)
    new_slugs = set(posts.keys())
    old_slugs = await _existing_post_slugs()
    for slug, post in posts.items():
        await redis_store.set(f"{POST_KEY_PREFIX}{slug}", post.model_dump_json())
    for orphan in old_slugs - new_slugs:
        await redis_store.delete(f"{POST_KEY_PREFIX}{orphan}")
    await redis_store.set(INDEX_KEY, _serialize_index(posts))
    return SyncResult(synced=sorted(posts.keys()), skipped=skipped)
