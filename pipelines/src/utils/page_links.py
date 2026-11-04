"""Every link on a page with its anchor text, from the raw HTML so menus count. Which to follow is
the caller's decision."""

from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict
from shared.utils.url_utils import is_web_url


class PageLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    text: str = ""


def page_links(html: bytes, base: str) -> List[PageLink]:
    """One per url, in page order. Its anchors' texts are joined: "Read more" and "City Charter"
    can point at the same page."""
    texts: dict[str, str] = {}
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        url = urljoin(base, str(anchor["href"]).split("#")[0])
        if is_web_url(url):
            texts[url] = f"{texts.get(url, '')} {anchor.get_text(' ', strip=True)}".strip()
    return [PageLink(url=url, text=text) for url, text in texts.items()]
