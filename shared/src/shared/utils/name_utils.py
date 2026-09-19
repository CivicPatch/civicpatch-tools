import re
import unicodedata
from typing import Protocol, Sequence

from Levenshtein import distance as levenshtein_distance
from nameparser import HumanName
from nameparser.config import Constants
from nicknames import NickNamer

from shared.schemas import Person


class Named(Protocol):
    name: str


# nameparser only reads straight quotes as nickname markers.
_STRAIGHT_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
# A credential split by a space at the end of a name. Initials ("A. M") never match.
_SPLIT_CREDENTIAL = re.compile(
    r"""
    \s+
    ([a-z]{2,})    # the abbreviation, two letters or more: "Ed", "Ph"
    \.\s+          # its period and the space nameparser splits on: ". "
    ([a-z])        # one letter: "D"
    \.?$           # an optional closing period, at the very end: "D."
    """,
    re.IGNORECASE | re.VERBOSE,
)
_NAME_PUNCTUATION = re.compile(
    r"""
    [.,]    # "Hale, Jr." compares as "Hale Jr", and "W." as "W"
    """,
    re.VERBOSE,
)
_NOT_WORD_OR_SPACE = re.compile(
    r"""
    [^\w\s]    # anything but a letter, digit or space: "D'Agostino" searches as "DAgostino"
    """,
    re.VERBOSE,
)
_GENERATIONAL_SUFFIXES = {"jr", "jnr", "junior", "sr", "snr", "senior", "i", "ii", "iii", "iv", "v"}


def _name_constants() -> Constants:
    constants = Constants()
    # Usually Mohammed, not a title.
    constants.titles.remove("md")
    return constants


_NAME_CONSTANTS = _name_constants()
_NICKNAMES = NickNamer()


def _is_kept(char: str) -> bool:
    # Lm is ʻokina-style marks, which the ASCII-only version this replaced also dropped.
    return char.isascii() or (char.isalnum() and unicodedata.category(char) != "Lm")


def _strip_accents(s: str) -> str:
    """Accents, invisible characters and non-ASCII punctuation go; letters in any script stay."""
    return "".join(char for char in unicodedata.normalize("NFKD", s) if _is_kept(char))


def _casefold(s: str) -> str:
    return _strip_accents(s).casefold()


def _token_key(token: str) -> str:
    """A middle name or suffix as compared: "Jr." and "jr" are the same."""
    return token.lower().strip().rstrip(".")


def _is_generational(suffix: str) -> bool:
    return _token_key(suffix) in _GENERATIONAL_SUFFIXES


def _without_titles_or_credentials(parsed: HumanName) -> HumanName:
    """Titles and credentials identify nobody; Jr. and Sr. do, wherever nameparser put them."""
    if parsed.first:
        first = parsed.first
        suffixes = parsed.title_list + parsed.suffix_list
    else:
        # "Hon Lien", "JR Gonzales": nameparser read the first name as a title.
        first = parsed.title
        suffixes = parsed.suffix_list
    return HumanName(
        first=first,
        middle=parsed.middle,
        last=parsed.last,
        suffix=", ".join(suffix for suffix in suffixes if _is_generational(suffix)),
        nickname=parsed.nickname,
        constants=_NAME_CONSTANTS,
    )


def _rejoin_split_credential(name: str) -> str:
    """nameparser splits on spaces, so it would read "Ed. D" as a middle name and a surname."""
    split = _SPLIT_CREDENTIAL.search(name)
    if split is None:
        return name
    joined = (split.group(1) + split.group(2)).lower()
    if joined not in _NAME_CONSTANTS.suffix_acronyms:
        return name
    return f"{name[: split.start()]} {split.group(1)}.{split.group(2)}."


def parse_name(name: str) -> HumanName:
    straightened = name.translate(_STRAIGHT_QUOTES).strip()
    rejoined = _rejoin_split_credential(straightened)
    return _without_titles_or_credentials(HumanName(rejoined, constants=_NAME_CONSTANTS))


def _without_leading_title(words: list[str], parsed: HumanName) -> list[str]:
    title_words = parsed.title.split()
    # No first name means the title is the first name: "Hon Lien".
    if not parsed.first or not title_words:
        return words
    leading = words[: len(title_words)]
    if [_token_key(word) for word in leading] != [_token_key(word) for word in title_words]:
        return words
    return words[len(title_words) :]


def _without_trailing_credentials(words: list[str], parsed: HumanName) -> list[str]:
    kept = list(words)
    while kept:
        last = kept[-1].rstrip(",")
        if last not in parsed.suffix_list or _is_generational(last):
            break
        kept.pop()
    return kept


def strip_titles_and_credentials(name: str) -> str:
    """The name as written, minus a leading title and trailing credentials.

    Edits the text rather than printing the parse, which would rewrite 'Jose "Chuy" Valerio'.
    """
    text = _rejoin_split_credential(name.strip())
    parsed = HumanName(text.translate(_STRAIGHT_QUOTES), constants=_NAME_CONSTANTS)
    words = _without_leading_title(text.split(), parsed)
    return " ".join(_without_trailing_credentials(words, parsed)).rstrip(",")


def reorder_name_if_inverted(name: str) -> str:
    """
    If a name is in 'Last, First' format (detected by comma), reorder to 'First Last'.
    HumanName detects the comma convention and str() outputs in First Last order.
    Names without a comma are returned unchanged.
    """
    if "," not in name:
        return name
    return str(HumanName(name)).strip()


def name_grouping_key(name: str) -> str:
    """Normalize name by removing accents, titles, suffixes, and extra whitespace, but preserving nickname."""
    hn = parse_name(name)
    parts = [hn.first, hn.middle, hn.last]
    if hn.nickname:
        parts.append(f'"{hn.nickname}"')
    base = " ".join(p for p in parts if p)
    return _strip_accents(base).lower().strip()


def normalize_text_for_search(text: str) -> str:
    """Normalize text for loose substring search: strips accents, punctuation, and lowercases."""
    return _NOT_WORD_OR_SPACE.sub("", _strip_accents(text)).lower()


def _comparison_key(name: str) -> str:
    parsed = parse_name(name)
    parts = [parsed.first, parsed.middle, parsed.last, parsed.suffix, parsed.nickname]
    unpunctuated = _NAME_PUNCTUATION.sub("", _casefold(" ".join(parts)))
    return " ".join(unpunctuated.split())


def same_name(name1: str, name2: str) -> bool:
    """Same parsed name, setting aside case, accents, punctuation, titles and credentials."""
    return _comparison_key(name1) == _comparison_key(name2)


def _within_one_edit(a: str, b: str) -> bool:
    return levenshtein_distance(a, b) <= 1


def _agree(a: str, b: str) -> bool:
    return bool(a) and bool(b) and _token_key(a) == _token_key(b)


def _conflict(a: str, b: str) -> bool:
    return bool(a) and bool(b) and _token_key(a) != _token_key(b)


def _middles_compatible(middle1: str, middle2: str) -> bool:
    """Equal, or one is the other's initial: "A." and "Alexander"."""
    m1 = _token_key(_casefold(middle1))
    m2 = _token_key(_casefold(middle2))
    if not m1 or not m2:
        return True
    if len(m1) == 1 or len(m2) == 1:
        return m1[0] == m2[0]
    return m1 == m2


def surname_key(name: str) -> str:
    return _casefold(parse_name(name).last)


def last_name_match(name1: str, name2: str) -> bool:
    """Return True if the last name components match (within one edit)."""
    p1 = parse_name(name1)
    p2 = parse_name(name2)
    return _within_one_edit(_casefold(p1.last), _casefold(p2.last))


def _is_short_form(short: str, full: str) -> bool:
    """ "Alex" of "Alexander". Three letters at least: "Al" starts too many names."""
    return len(short) >= 3 and full.startswith(short)


def _goes_by(first: str, other: HumanName) -> bool:
    """ "Gino" for 'Gene "Gino" Garcia', "Buddy" for "Ernest Buddy Mendes"."""
    return bool(first) and first in (_casefold(other.nickname), _casefold(other.middle))


def _first_names_compatible(p1: HumanName, p2: HumanName) -> bool:
    first1 = _casefold(p1.first)
    first2 = _casefold(p2.first)
    if _within_one_edit(first1, first2):
        return True
    if _is_short_form(first1, first2) or _is_short_form(first2, first1):
        return True
    return _goes_by(first1, p2) or _goes_by(first2, p1)


def _surname_words(part: str) -> list[str]:
    return _casefold(part).replace("-", " ").split()


def _starts_hyphenated(surname: str, prefix: str) -> bool:
    """ "Aguilera" of "Aguilera-Hernandez"."""
    parts = [_casefold(part) for part in surname.split("-")]
    return len(parts) > 1 and parts[0] == _casefold(prefix)


def _surnames_compatible(p1: HumanName, p2: HumanName) -> bool:
    if _within_one_edit(_casefold(p1.last), _casefold(p2.last)):
        return True
    # "Sheila Crippen Thomas" parses Crippen as a middle name; "Crippen-Thomas" does not.
    if _surname_words(f"{p1.middle} {p1.last}") == _surname_words(p2.last):
        return True
    if _surname_words(f"{p2.middle} {p2.last}") == _surname_words(p1.last):
        return True
    return _starts_hyphenated(p1.last, p2.last) or _starts_hyphenated(p2.last, p1.last)


def fuzzy_match(name1: str, name2: str) -> bool:
    p1 = parse_name(name1)
    p2 = parse_name(name2)
    if not _first_names_compatible(p1, p2):
        return False
    if not _surnames_compatible(p1, p2):
        return False
    if p1.middle and p2.middle and not _middles_compatible(p1.middle, p2.middle):
        return False
    if _conflict(p1.suffix, p2.suffix):
        return False
    return True


def same_surname(name1: str, name2: str) -> bool:
    return _surnames_compatible(parse_name(name1), parse_name(name2))


def _is_nickname_pair(first1: str, first2: str) -> bool:
    """ "Dave" and "David", either way round. Never two full names through a shared nickname."""
    return first2 in _NICKNAMES.canonicals_of(first1) or first1 in _NICKNAMES.canonicals_of(first2)


def nickname_tie(name1: str, name2: str) -> bool:
    """Same surname, first names the nickname data pairs: "Dave Polivy" and "David Polivy".

    Weak on its own: the data gives Bill and Robert as much weight as Dave and David, so
    `resolve_people_ids` trusts it only when nobody else could explain the pair.
    """
    p1 = parse_name(name1)
    p2 = parse_name(name2)
    if not _surnames_compatible(p1, p2) or _conflict(p1.suffix, p2.suffix):
        return False
    return _is_nickname_pair(_casefold(p1.first), _casefold(p2.first))


def fuzzy_match_score(name1: str, name2: str) -> int:
    p1 = parse_name(name1)
    p2 = parse_name(name2)
    score = 0
    if _casefold(p1.first) == _casefold(p2.first):
        score += 1
    if _casefold(p1.last) == _casefold(p2.last):
        score += 1
    if _agree(_casefold(p1.middle), _casefold(p2.middle)):
        score += 1
    if _agree(p1.suffix, p2.suffix):
        score += 1
    return score


def person_list_to_identities(people: list[Person]) -> dict[str, list[str]]:
    """Each published person's name, mapped to their other names."""
    return {person.name: person.other_names for person in people if person.name}


def get_person_name(person: dict | Named) -> str:
    return (person.get("name") or "") if isinstance(person, dict) else person.name


def best_identity_match(name: str, identities: dict[str, list[str]]) -> str | None:
    best_canonical = None
    best_score = 0
    for canonical, aliases in identities.items():
        for candidate in [canonical] + aliases:
            if fuzzy_match(name, candidate):
                score = fuzzy_match_score(name, candidate)
                if score > best_score:
                    best_score = score
                    best_canonical = canonical
    return best_canonical


def exact_identity_match(name: str, identities: dict[str, list[str]]) -> str | None:
    for canonical, aliases in identities.items():
        if any(same_name(name, candidate) for candidate in [canonical] + aliases):
            return canonical
    return None


def _fuzzy_canonical_match(name: str, canonicals: list[str]) -> str | None:
    for canonical in canonicals:
        if fuzzy_match(name, canonical):
            return canonical
    return None


def build_canonical_map(
    all_people: Sequence[dict | Named], identities: dict[str, list[str]]
) -> dict[str, str]:
    """
    Map every name to its canonical form, using identities and fuzzy matching across all sources.
    Priority:
    1. Exact match against identity canonicals/aliases
    2. Best fuzzy match against identities (scored — picks most specific match)
    3. Fuzzy match against already-collected canonicals
    4. New canonical
    """
    canonicals: list[str] = []
    name_to_canonical: dict[str, str] = {}

    for person in all_people:
        name = get_person_name(person)
        canonical = exact_identity_match(name, identities)
        if canonical is None:
            canonical = best_identity_match(name, identities)
        if canonical is None:
            canonical = _fuzzy_canonical_match(name, canonicals)
        if canonical is None:
            canonicals.append(name)
            canonical = name
        name_to_canonical[name] = canonical

    return name_to_canonical
