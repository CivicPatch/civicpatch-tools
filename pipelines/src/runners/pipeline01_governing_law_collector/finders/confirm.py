"""Whether a page's text is this place's charter and not a page that merely mentions one: long,
sectioned, named for the place, not a soft 404. The thresholds were measured: every readable
charter clears them and no false hit (news item, "Government" page, move notice) does."""

import re
from typing import List

from shared.utils.government_forms import LEGAL_STATUS_WORDS, name_suffix

MIN_CHARTER_CHARS = 5_000
MIN_SECTION_MARKERS = 15
# A soft 404 says so in its first lines; a charter never does.
TITLE_CHARS = 200
_SECTION_MARKER = re.compile(r"\b(section|article|sec\.)\b|§", re.IGNORECASE)
_NOT_FOUND = re.compile(r"not found|404 error|error 404", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


def is_charter(markdown: str, name: str, charter_terms: List[str]) -> bool:
    text = _WHITESPACE.sub(" ", markdown).lower()
    return (
        len(text) >= MIN_CHARTER_CHARS
        and any(term.lower() in text for term in charter_terms)
        and place_word(name) in text
        and len(_SECTION_MARKER.findall(markdown)) >= MIN_SECTION_MARKERS
        and not _NOT_FOUND.search(text[:TITLE_CHARS])
    )


def place_word(name: str) -> str:
    """"Lane County" -> "lane", "Lakeview town" -> "lakeview", "Portland" -> "portland": the name
    a charter writes, without the registry's legal status word."""
    suffix = name_suffix(name)
    if suffix in LEGAL_STATUS_WORDS:
        return name[: -len(suffix)].strip().lower()
    return name.strip().lower()
