"""A governing-law page's cached text: markdown, content-addressed. The key says nothing the
row does not already (source url, when, which jurisdiction), so one text collected for many
jurisdictions is stored once, and a re-fetch of an unchanged text is idempotent."""

import hashlib
import re

CACHE_PREFIX = "governing_law"
CONTENT_TYPE = "text/markdown"

# A tag with a name, closing or not: what a page stripped to its text never contains.
_HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(\s[^<>]*)?>")


def page_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def cache_path(page_hash: str) -> str:
    return f"{CACHE_PREFIX}/{page_hash}.md"


def carries_html(text: str) -> bool:
    return _HTML_TAG.search(text) is not None
