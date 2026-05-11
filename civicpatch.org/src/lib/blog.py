import re
from datetime import date
from pathlib import Path

import frontmatter
import markdown as md_lib

_BLOG_DIR = Path(__file__).parent.parent.parent / "blog"


def _slug(filename: str) -> str:
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", filename.removesuffix(".md"))


def _date(filename: str) -> date:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    assert m is not None
    return date.fromisoformat(m.group(1))


def _parse_post(path: Path) -> dict | None:
    try:
        post = frontmatter.load(str(path))
    except Exception:
        return None
    _md = md_lib.Markdown(extensions=["tables", "toc"], extension_configs={"toc": {"toc_depth": 2}})
    _content_html = _md.convert(post.content)
    _toc = getattr(_md, "toc", "")
    return {
        "slug": _slug(path.name),
        "title": post.get("title", path.stem),
        "date": _date(path.name),
        "description": post.get("description", ""),
        "author": post.get("author", "The CivicPatch Team"),
        "draft": bool(post.get("draft", False)),
        "updated_at": post.get("updated_at"),
        "content_html": _content_html,
        "toc_html": _toc if "<li>" in _toc else "",
    }


def get_all_posts() -> list[dict]:
    posts = []
    for path in sorted(_BLOG_DIR.glob("*.md"), reverse=True):
        post = _parse_post(path)
        if post and not post["draft"]:
            posts.append(post)
    return posts


def get_post(slug: str) -> dict | None:
    for path in _BLOG_DIR.glob("*.md"):
        if _slug(path.name) == slug:
            return _parse_post(path)
    return None
