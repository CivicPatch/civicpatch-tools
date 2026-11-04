"""Whether a page is the law a search wants: a free filter, then Jev names the document. Measured
against blind labels (`.scratch/logs/jev-accuracy/score.txt`), it rejects the drafts, model charters
and cable franchises a count of section markers let through."""

import re
from typing import Any, Dict, List

from services.open_router import decisions
from ..schemas import LawTarget
from .crawl import PageTest

MIN_CHARS = 1_000
# Confidence moves by up to 0.07 on a repeat, and a real page lost here cannot be recovered later.
MIN_CONFIDENCE = 0.6
PROMPT_NAME = "law_page_check"
OPENING_CHARS = 3_000
MAX_HEADINGS = 40
HEADING_CHARS = 120
LABEL_CHARTER = "charter"
LABEL_AMENDMENT = "amendment"
CHARTER_LABELS = [LABEL_CHARTER, LABEL_AMENDMENT]
_LAW_WORDS = re.compile(r"\b(charter|statutes?|constitution|ordinances?|municipal code|county code|revised code)\b", re.IGNORECASE)
_HEADING = re.compile(r"^(#{1,6} |\*\*|- \*\*|(section|article|chapter|sec\.)\s|§)", re.IGNORECASE)
_CRITERIA = {
    LABEL_CHARTER: "The place's own charter or home rule charter, in force, in whole or in part.",
    LABEL_AMENDMENT: "An adopted amendment to the place's charter, published on its own.",
    "proposed": "A draft, ballot notice, review committee paper or proposal about a charter, not adopted law.",
    "other_place": "A charter or law of some other place.",
    "code": "A municipal or county code of ordinances, not the charter.",
    "statute": "A state statute or chapter of state law.",
    "constitution": "A state constitution.",
    "news": "News, minutes, agendas, or a page that merely mentions a charter.",
    "other": "Anything else.",
}


def might_be_law(markdown: str) -> bool:
    return len(markdown) >= MIN_CHARS and _LAW_WORDS.search(markdown) is not None


def headings(markdown: str) -> List[str]:
    lines = (line.strip() for line in markdown.splitlines())
    return [line[:HEADING_CHARS] for line in lines if _HEADING.match(line)][:MAX_HEADINGS]


def document_state(markdown: str, url: str, name: str) -> Dict[str, Any]:
    return {"place": name, "url": url, "characters": len(markdown), "opening": markdown[:OPENING_CHARS], "headings": headings(markdown)}


def page_test(target: LawTarget, name: str, pipeline_run_id: str, jurisdiction_ocdid: str) -> PageTest:
    async def is_target(markdown: str, url: str) -> bool:
        if not might_be_law(markdown):
            return False
        instructions = f"What is this document, as it concerns {name}?"
        answer = await decisions.choose(pipeline_run_id, jurisdiction_ocdid, PROMPT_NAME, url, document_state(markdown, url, name), instructions, _CRITERIA)
        return answer.choice in target.kept_labels and (answer.confidence or 0) >= MIN_CONFIDENCE

    return is_target
