"""The state's own list of charters decides: listed means a charter at its link, not listed means
the classification's general law. How a state words and links its list is config, not code."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from ..fetchers import plain
from ..schemas import FinderAnswer
from shared.schemas import FoundBy
from shared.utils.government_forms import name_suffix
from shared.utils.layered_config import PLACE_PLACEHOLDER, CharterLinkList, GoverningLawConfig, resolve_classification


async def find(governing_law: GoverningLawConfig, name: str) -> FinderAnswer:
    charter_link_list = governing_law.charter_link_list
    assert charter_link_list is not None, "finders.find calls this only for a state with a link list"
    index = await plain.fetch(charter_link_list.url)
    classification_id = resolve_classification(governing_law, name, None)
    return FinderAnswer(
        found_by=FoundBy.STATE_INDEX,
        classification=classification_id,
        charter_urls=charter_links(charter_link_list, index.body, index.url, name),
        general_law_urls=governing_law.classifications[classification_id].general_law if classification_id else [],
    )


def charter_links(charter_link_list: CharterLinkList, index_html: bytes, index_url: str, name: str) -> list[str]:
    """Every link whose whole text is this place's charter title, in index order, each taken to
    its full text where the state links a contents page."""
    links = []
    for anchor in BeautifulSoup(index_html, "html.parser").find_all("a", href=True):
        if charter_title_matches(charter_link_list.title, name, anchor.get_text(" ", strip=True)):
            links.append(_full_text(charter_link_list, urljoin(index_url, str(anchor["href"]))))
    return links


def _full_text(charter_link_list: CharterLinkList, url: str) -> str:
    link = charter_link_list.text_link
    return url.replace(link.old, link.new, 1) if link else url


TITLE_PLACEHOLDERS = ("{lsad}", PLACE_PLACEHOLDER, "{*}")


def charter_title_matches(title: str, name: str, link_text: str) -> bool:
    """Whether an index link's whole text is this jurisdiction's charter title, ignoring case and
    spacing. A title with anything more, "[Repealed]" say, does not match."""
    lsad = name_suffix(name)
    values = {"{lsad}": lsad, PLACE_PLACEHOLDER: name[: -len(lsad)].strip() if lsad else name, "{*}": None}
    pattern = ""
    for part in re.split(r"(\{lsad\}|\{place\}|\{\*\})", _spaced(title)):
        if part in TITLE_PLACEHOLDERS:
            value = values[part]
            pattern += ".+?" if value is None else re.escape(_spaced(value))
        else:
            pattern += re.escape(part)
    return re.fullmatch(pattern, _spaced(link_text), re.IGNORECASE) is not None


def _spaced(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
