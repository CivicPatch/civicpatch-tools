"""Whether a quote from the law supports a claim about a post: the quote is in the text (rule 1),
names the role (rule 2) and names how it is filled (rule 3). The model's quote only locates the
clause; the stored quote is the shortest context around it that passes, verbatim from the text."""

import re

from shared.schemas import SelectionMethod

_WHITESPACE = re.compile(r"\s+")
# A period ends a sentence when a capital or "(1)" follows, but not after a section number
# ("§ 871."), initials ("V.S.A."), or the session-law abbreviations ("No. M-19 (Adj. Sess.)").
_SENTENCE_END = re.compile(r"(?<![\d§])(?<!\b[A-Z])(?<!\bNo)(?<!\bAdj)(?<!\bSess)(?<!\beff)\.\s+(?=[A-Z(])")
_SECTION_HEADING = re.compile(r"^- \*\*§")
# Past this a section says too much for its method to be about this role.
WIDEST_QUOTE_CHARS = 1500

METHOD_WORDS: dict[SelectionMethod, tuple[str, ...]] = {
    SelectionMethod.ELECTED_BY_VOTERS: ("elect", "elected", "election", "elections", "chosen", "vote"),
    SelectionMethod.ELECTED_BY_MEMBERS: (
        "elect", "elected", "election", "chosen", "vote", "from its number", "from among its members",
    ),
    SelectionMethod.APPOINTED: ("appoint", "appointed", "appointment", "appoints", "appointive"),
}


def normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def quote_in_text(quote: str, text: str) -> bool:
    return normalise(quote) in normalise(text)


def role_named_in_quote(quote: str, names: list[str]) -> bool:
    """Case- and spacing-insensitive: "Selectboard" names "select board"."""
    return any(_name_pattern(name).search(quote) for name in names)


def method_named_in_quote(quote: str, method: SelectionMethod) -> bool:
    return any(_phrase_pattern(word).search(quote) for word in METHOD_WORDS[method])


def supporting_quote(text: str, locator: str, names: list[str], method: SelectionMethod) -> str | None:
    """The sentence around the locator, else its section's body, else that body under its
    heading: the first that names the role and the method. None when the locator is not in the
    text or nothing up to the widest rung passes."""
    span = _locate(text, locator)
    if span is None:
        return None
    for rung in (_sentence(text, span), _line(text, span), _section(text, span)):
        quote = normalise(rung)
        if len(quote) > WIDEST_QUOTE_CHARS:
            return None
        if role_named_in_quote(quote, names) and method_named_in_quote(quote, method):
            return quote
    return None


def _name_pattern(name: str) -> re.Pattern[str]:
    letters = [re.escape(letter) for letter in name.replace(" ", "")]
    return re.compile(r"\b" + r"\s*".join(letters) + r"s?\b", re.IGNORECASE)


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(r"\b" + r"\s+".join(map(re.escape, phrase.split())) + r"\b", re.IGNORECASE)


def _locate(text: str, locator: str) -> tuple[int, int] | None:
    words = normalise(locator).split(" ")
    match = re.search(r"\s+".join(map(re.escape, words)), text)
    return match.span() if match else None


def _line_bounds(text: str, span: tuple[int, int]) -> tuple[int, int]:
    start = text.rfind("\n", 0, span[0]) + 1
    end = text.find("\n", span[1])
    return start, len(text) if end == -1 else end


def _line(text: str, span: tuple[int, int]) -> str:
    start, end = _line_bounds(text, span)
    return text[start:end]


def _sentence(text: str, span: tuple[int, int]) -> str:
    line_start, line_end = _line_bounds(text, span)
    start = line_start
    # Over the whole line: an end's lookahead must see the capital the locator starts with.
    for match in _SENTENCE_END.finditer(text, line_start, line_end):
        if match.end() > span[0]:
            break
        start = match.end()
    # From the locator's last character, so a locator ending in its own period ends there.
    after = _SENTENCE_END.search(text, span[1] - 1, line_end)
    end = after.start() + 1 if after else line_end
    return text[start:end]


def _section(text: str, span: tuple[int, int]) -> str:
    """The body line with the `- **§ N. Heading**` line above it, as plan 1's markdown writes a section."""
    start, end = _line_bounds(text, span)
    heading_start = text.rfind("\n", 0, max(start - 1, 0)) + 1
    heading = text[heading_start:start]
    if _SECTION_HEADING.match(heading):
        return text[heading_start:end]
    return text[start:end]
