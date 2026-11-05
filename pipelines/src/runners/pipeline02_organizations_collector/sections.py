"""What of a jurisdiction's cached law the model reads: all of it when it fits, else the sections
picked from their headings. Pure: markdown in, sections out. A wrong pick can miss a claim but
never make one, since VERIFY checks every quote against the full text."""

import re
from typing import List
from urllib.parse import urlparse

from pydantic import BaseModel
from semantic_text_splitter import TextSplitter
from .section_formats import SECTION_FORMATS, SectionFormat
from shared.schemas import GoverningLaw, GoverningLawKind
from shared.utils.layered_config import GovernedBy, GoverningLawConfig

# Whole text beat every pick on laws up to Burlington's 374k, at under 2 cents a place.
WHOLE_TEXT_CHARS = 400_000


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


# A page with no known format splits at the law's own headings: `CHAPTER II`, `Section 5.`,
# `§ 101.`, `221.160`. A comma or lower-case word after the number is a wrapped reference.
_OPENING = r"[^\w\n]*"
_NOT_REFERENCE = r"(?!,|[ \t]+[a-z])"
_GROUP_LINE = re.compile(rf"(?m:^{_OPENING}(?i:chapter|article|part|title|subchapter)\s+(?i:[ivxlc\d]+)\b{_NOT_REFERENCE})")
_SECTION_LINE = re.compile(
    rf"(?m:^{_OPENING}(?i:§+|section|sec\.)\s*\d+(?:[-.]\d+)*\b{_NOT_REFERENCE})|(?m:^{_OPENING}\d+(?:\.\d+)+\.?\s+[A-Z])"
    # A markdown heading, as the publisher converters write them, whatever the state's wording.
    r"|(?m:^#{1,6}[ \t]+\S)"
)
# Over this share of a page's sections without a heading, its headings went unrecognised.
UNHEADED_WARNING_SHARE = 0.5
# A longer section is cut into parts of this size, each under its own heading.
SECTION_MAX_CHARS = 4_000
# "Chapter I" alone takes its title from the next line.
_BARE_HEADING_CHARS = 16
_HEADING_CHARS = 90
# Text under no recognised heading is listed by its first line, so the pick can still tell it apart.
NO_HEADING = "(no heading)"
_MARKUP = re.compile(r"[*#_`\\]+")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")

# The charter first: it governs, and the general law applies where it says nothing.
PAGE_KIND_ORDER = (GoverningLawKind.CHARTER, GoverningLawKind.GENERAL_LAW)
PAGE_KIND_TITLES = {GoverningLawKind.CHARTER: "# Charter", GoverningLawKind.GENERAL_LAW: "# General law"}


class GoverningLawPage(BaseModel):
    # Its `governing_law_source_pages` row: what a verified quote cites.
    id: str
    source_url: str
    text: str


def page_kind(page: GoverningLawPage, governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None) -> GoverningLawKind:
    """A charter jurisdiction's pages are its charter, but for those at its classification's general
    law urls; a general law jurisdiction's are all statute."""
    if governing_law.kind != GoverningLawKind.CHARTER:
        return GoverningLawKind.GENERAL_LAW
    return GoverningLawKind.GENERAL_LAW if page.source_url in _general_law_urls(governing_law, governing_law_config) else GoverningLawKind.CHARTER


def pages_by_kind(
    pages: List[GoverningLawPage], governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None
) -> List[tuple[GoverningLawKind, List[GoverningLawPage]]]:
    """In `PAGE_KIND_ORDER`, each kind's pages in their stored order; a kind with none is left out.
    Where a charter replaces the general law, a charter jurisdiction's statute pages are left out."""
    grouped: List[tuple[GoverningLawKind, List[GoverningLawPage]]] = []
    for kind in PAGE_KIND_ORDER:
        kind_pages = [page for page in pages if page_kind(page, governing_law, governing_law_config) == kind]
        if kind_pages:
            grouped.append((kind, kind_pages))
    if _charter_replaces_general_law(governing_law, governing_law_config) and grouped and grouped[0][0] == GoverningLawKind.CHARTER:
        return grouped[:1]
    return grouped


def _charter_replaces_general_law(governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None) -> bool:
    if governing_law_config is None or governing_law.classification is None:
        return False
    classification = governing_law_config.classifications.get(governing_law.classification)
    return classification is not None and classification.governed_by == GovernedBy.CHARTER_ELSE_GENERAL_LAW


def _general_law_urls(governing_law: GoverningLaw, governing_law_config: GoverningLawConfig | None) -> List[str]:
    if governing_law_config is None or governing_law.classification is None:
        return []
    classification = governing_law_config.classifications.get(governing_law.classification)
    return classification.general_law if classification else []


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
    """Every section of every page, numbered across pages: by the publisher's format where it is
    known, else at the law's own headings."""
    sections: List[Section] = []
    for page in pages:
        section_format = SECTION_FORMATS.get(urlparse(page.source_url).hostname or "")
        first_number = len(sections) + 1
        if section_format is None:
            sections.extend(_headed_sections(page.text, first_number))
        else:
            sections.extend(_page_sections(page.text, section_format, first_number))
    return sections


def unheaded_share(sections: List[Section]) -> float:
    if not sections:
        return 0.0
    return sum(section.heading.startswith(NO_HEADING) for section in sections) / len(sections)


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


def _headed_sections(page: str, first_number: int) -> List[Section]:
    """Every character lands in a section, so a wrong split can cost a pick but never text."""
    found: List[Section] = []
    group = ""
    starts = _heading_starts(page)
    for start, end in zip(starts, [*starts[1:], len(page)]):
        headed = bool(_SECTION_LINE.match(page, start) or _GROUP_LINE.match(page, start))
        heading = _heading_at(page, start) if headed else ""
        if _GROUP_LINE.match(page, start):
            group = heading
        for part in _parts(page[start:end]):
            label = heading or f"{NO_HEADING} {_preview(part)}"
            found.append(Section(id=f"H{first_number + len(found):04d}", group=group, heading=label, text=part))
    return found


def _preview(part: str) -> str:
    first_line = next((line for line in part.splitlines() if line.strip()), "")
    return _clean_heading(first_line)[:_HEADING_CHARS]


def _heading_starts(page: str) -> List[int]:
    headings = {match.start() for pattern in (_GROUP_LINE, _SECTION_LINE) for match in pattern.finditer(page)}
    return sorted(headings | {0})


def _heading_at(page: str, start: int) -> str:
    lines = page[start:start + 2 * _HEADING_CHARS].split("\n")
    heading = _clean_heading(lines[0])
    if len(heading) < _BARE_HEADING_CHARS and len(lines) > 1:
        heading = f"{heading} {_clean_heading(lines[1])}".strip()
    return heading[:_HEADING_CHARS]


def _clean_heading(line: str) -> str:
    return " ".join(_MARKUP.sub("", _LINK.sub(r"\1", line)).split()).strip(" -")


def _parts(text: str) -> List[str]:
    if len(text) <= SECTION_MAX_CHARS:
        return [text]
    return TextSplitter(SECTION_MAX_CHARS, trim=False).chunks(text)


def _with_body(found: List[Section], body: List[str]) -> List[Section]:
    if not found or not body:
        return found
    last = found[-1]
    return [*found[:-1], last.model_copy(update={"text": "\n".join([last.text, *body])})]
