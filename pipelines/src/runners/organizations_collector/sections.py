"""What of a jurisdiction's cached law the model reads: all of it when it fits, else the sections
picked from their headings. Pure: markdown in, sections out. A wrong pick can miss a claim but
never make one, since VERIFY checks every quote against the full text."""

import re
from typing import List
from urllib.parse import urlparse

from pydantic import BaseModel
from runners.organizations_collector.section_formats import SECTION_FORMATS, SectionFormat

# Most charters fit (Vermont's median is 21k chars); Burlington's 374k does not.
WHOLE_TEXT_CHARS = 110_000


# When the pick names nothing: headings about the governing body and its officers, not its
# boards, money or utilities. From the prototypes' heading ranking (charter-loop-4).
_GOVERNMENT_WORDS = (
    "council", "mayor", "selectboard", "select board", "trustee", "officers", "elect",
    "composition", "presid", "chair", "organization", "aldermen",
)
_OTHER_WORDS = (
    "commission", "pension", "retire", "civil service", "bond", "budget", "tax", "water", "sewer",
    "school", "library", "airport", "parks", "fire", "police", "cemetery", "street",
)
# "Board of Aldermen" is the governing body; any other "Board of" is not.
_OTHER_BOARD = re.compile(r"board of (?!aldermen)", re.IGNORECASE)


class GoverningLawPage(BaseModel):
    source_url: str
    text: str


class Section(BaseModel):
    # Shown to the model instead of a number: it answered with the § number when shown a list
    # index, shifting every pick by one.
    id: str
    # The subchapter it sits in, "" before the first.
    group: str
    heading: str
    text: str


def fits_whole(markdown: str) -> bool:
    return len(markdown) <= WHOLE_TEXT_CHARS


def split_sections(pages: List[GoverningLawPage]) -> List[Section]:
    """Every section of every page whose publisher's format is known, numbered across pages."""
    sections: List[Section] = []
    for page in pages:
        section_format = SECTION_FORMATS.get(urlparse(page.source_url).hostname or "")
        if section_format is None:
            continue
        sections.extend(_page_sections(page.text, section_format, first_number=len(sections) + 1))
    return sections


def heading_listing(sections: List[Section]) -> str:
    lines: List[str] = []
    group = None
    for section in sections:
        if section.group != group:
            group = section.group
            if group:
                lines.append(group)
        lines.append(f"  {section.id}: {section.heading}")
    return "\n".join(lines)


def picked(sections: List[Section], ids: List[str]) -> List[Section]:
    """In document order, whatever order the model named them in; ids it made up are dropped."""
    wanted = set(ids)
    return [section for section in sections if section.id in wanted]


def keyword_sections(sections: List[Section]) -> List[Section]:
    return [section for section in sections if _names_the_government(section.heading)]


def _names_the_government(heading: str) -> bool:
    lowered = heading.lower()
    if _OTHER_BOARD.search(lowered) or any(word in lowered for word in _OTHER_WORDS):
        return False
    return any(word in lowered for word in _GOVERNMENT_WORDS)


def joined(sections: List[Section]) -> str:
    return "\n".join(section.text for section in sections)


def _page_sections(page: str, section_format: SectionFormat, first_number: int) -> List[Section]:
    """A page's text before its first section, the site's header and navigation, belongs to none."""
    found: List[Section] = []
    body: List[str] = []
    group = ""
    for line in page.splitlines():
        group_line = section_format.group.match(line)
        anchor = section_format.anchor.match(line)
        if group_line:
            group = group_line.group(1).strip()
        elif anchor:
            found = _with_body(found, body)
            body = []
            number = first_number + len(found)
            found.append(Section(id=f"H{number:04d}", group=group, heading=anchor.group(1).strip(), text=line))
        elif found:
            body.append(line)
    return _with_body(found, body)


def _with_body(found: List[Section], body: List[str]) -> List[Section]:
    if not found or not body:
        return found
    last = found[-1]
    return [*found[:-1], last.model_copy(update={"text": "\n".join([last.text, *body])})]
