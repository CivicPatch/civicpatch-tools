import re
from datetime import date
from pathlib import Path

import frontmatter
import markdown as md_lib

from schemas.blog import BlogIndexEntry, BlogPost

_BLOG_DIR = Path(__file__).parent.parent.parent / "blog"


def _slug(filename: str) -> str:
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", filename.removesuffix(".md"))


def _date(filename: str) -> date:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    assert m is not None
    return date.fromisoformat(m.group(1))


def _parse_post(path: Path) -> BlogPost | None:
    try:
        post = frontmatter.load(str(path))
    except Exception:
        return None
    _md = md_lib.Markdown(extensions=["tables", "toc"], extension_configs={"toc": {"toc_depth": 2}})
    content_html = _md.convert(post.content)
    toc = getattr(_md, "toc", "")
    return BlogPost.model_validate(
        {
            "slug": _slug(path.name),
            "title": post.metadata.get("title", path.stem),
            "date": _date(path.name),
            "description": post.metadata.get("description", ""),
            "author": post.metadata.get("author", "The CivicPatch Team"),
            "draft": bool(post.metadata.get("draft", False)),
            "updated_at": post.metadata.get("updated_at"),
            "content_html": content_html,
            "toc_html": toc if "<li>" in toc else "",
        }
    )


def _to_index_entry(post: BlogPost) -> BlogIndexEntry:
    return BlogIndexEntry(
        slug=post.slug,
        title=post.title,
        date=post.date,
        description=post.description,
        author=post.author,
    )


def get_all_posts() -> list[BlogIndexEntry]:
    entries: list[BlogIndexEntry] = []
    for path in sorted(_BLOG_DIR.glob("*.md"), reverse=True):
        post = _parse_post(path)
        if post and not post.draft:
            entries.append(_to_index_entry(post))
    return entries


def get_post(slug: str) -> BlogPost | None:
    for path in _BLOG_DIR.glob("*.md"):
        if _slug(path.name) == slug:
            return _parse_post(path)
    return None
