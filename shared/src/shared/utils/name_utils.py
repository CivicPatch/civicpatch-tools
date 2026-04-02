import re
import unicodedata
from typing import Dict, List, Protocol

from nameparser import HumanName

from shared.schemas import Person


class HasName(Protocol):
    """Protocol for objects with a name field."""

    name: str


def person_list_to_identities(people: List[Person]) -> Dict[str, List[str]]:
    """Convert a list of people dicts to an identities mapping."""
    return {person.name: person.other_names for person in people if person.name}


def collect_other_names(group: List[HasName], canonical_name: str) -> List[str]:
    """Collect all names from a group, excluding the canonical name."""
    all_names = {p.name for p in group if p.name}
    for p in group:
        if p.other_names:
            all_names.update(p.other_names)
    all_names.discard(canonical_name)
    return list(all_names)


def get_person_name(p) -> str:
    return p.get("name") if isinstance(p, dict) else p.name


def parse_name(name: str) -> HumanName:
    """Parse a name string into components."""
    return HumanName(name)


def exact_match(name1: str, name2: str) -> bool:
    """Exact name comparison (case-insensitive, whitespace-normalized)."""
    return _casefold(name1).strip() == _casefold(name2).strip()


def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _casefold(s: str) -> str:
    return _strip_accents(s).lower()


def _normalize_suffix(suffix: str) -> str:
    """Normalize suffix for comparison (e.g. 'Jr.' -> 'jr', 'Jr' -> 'jr')."""
    return suffix.lower().strip().rstrip(".")


def _within_one_edit(a: str, b: str) -> bool:
    """Return True if a and b differ by at most one insertion, deletion, or substitution."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    i = j = diffs = 0
    while i < la and j < lb:
        if a[i] != b[j]:
            diffs += 1
            if diffs > 1:
                return False
            if la == lb:
                i += 1
            j += 1
        else:
            i += 1
            j += 1
    return True


def last_name_match(name1: str, name2: str) -> bool:
    """Return True if the last name components match (within one edit)."""
    p1 = parse_name(name1)
    p2 = parse_name(name2)
    return _within_one_edit(_casefold(p1.last), _casefold(p2.last))


def fuzzy_match(name1: str, name2: str) -> bool:
    p1 = parse_name(name1)
    p2 = parse_name(name2)

    if not _within_one_edit(_casefold(p1.first), _casefold(p2.first)) or not _within_one_edit(_casefold(p1.last), _casefold(p2.last)):
        return False
    if p1.middle and p2.middle and _normalize_suffix(_casefold(p1.middle)) != _normalize_suffix(_casefold(p2.middle)):
        return False
    if (
        p1.suffix
        and p2.suffix
        and _normalize_suffix(p1.suffix) != _normalize_suffix(p2.suffix)
    ):
        return False

    return True


def _fuzzy_match_score(name1: str, name2: str) -> int:
    p1 = parse_name(name1)
    p2 = parse_name(name2)
    score = 0
    if _casefold(p1.first) == _casefold(p2.first):
        score += 1
    if _casefold(p1.last) == _casefold(p2.last):
        score += 1
    if p1.middle and p2.middle and _normalize_suffix(_casefold(p1.middle)) == _normalize_suffix(_casefold(p2.middle)):
        score += 1
    if (
        p1.suffix
        and p2.suffix
        and _normalize_suffix(p1.suffix) == _normalize_suffix(p2.suffix)
    ):
        score += 1
    return score


def reorder_name_if_inverted(name: str) -> str:
    """
    If a name is in 'Last, First' format (detected by comma), reorder to 'First Last'.
    HumanName detects the comma convention and str() outputs in First Last order.
    Names without a comma are returned unchanged.
    """
    if "," not in name:
        return name
    return str(HumanName(name)).strip()


def normalize_text_for_search(text: str) -> str:
    """Normalize text for loose substring search: strips accents, punctuation, and lowercases."""
    return re.sub(r"[^\w\s]", "", _strip_accents(text)).lower()


def normalize_name(name: str) -> str:
    """Normalize name by removing accents, titles, suffixes, and extra whitespace, but preserving nickname."""
    name = name.replace('\u201C', '"').replace('\u201D', '"').replace('\u2018', "'").replace('\u2019', "'")
    hn = HumanName(name)
    parts = [hn.first, hn.middle, hn.last]
    if hn.nickname:
        parts.append(f'"{hn.nickname}"')
    base = " ".join(p for p in parts if p)
    return _strip_accents(base).lower().strip()


def best_identity_match(name: str, identities: Dict[str, List[str]]) -> str | None:
    best_canonical = None
    best_score = 0
    for canonical, aliases in identities.items():
        for candidate in [canonical] + aliases:
            if fuzzy_match(name, candidate):
                score = _fuzzy_match_score(name, candidate)
                if score > best_score:
                    best_score = score
                    best_canonical = canonical
    return best_canonical


def build_canonical_map(
    all_people: List[dict], identities: Dict[str, List[str]]
) -> Dict[str, str]:
    """
    Map every name to its canonical form, using identities and fuzzy matching across all sources.
    Priority:
    1. Exact match against identity canonicals/aliases
    2. Best fuzzy match against identities (scored — picks most specific match)
    3. Fuzzy match against already-collected canonicals
    4. New canonical
    """
    canonicals = []
    name_to_canonical = {}

    for person in all_people:
        name = get_person_name(person)
        found = False

        if identities:
            # 1. Exact match against identities
            for canonical, aliases in identities.items():
                if exact_match(name, canonical) or any(
                    exact_match(name, alias) for alias in aliases
                ):
                    name_to_canonical[name] = canonical
                    found = True
                    break
            if found:
                continue

            # 2. Best fuzzy match against identities (scored)
            best_canonical = best_identity_match(name, identities)
            if best_canonical:
                name_to_canonical[name] = best_canonical
                continue

        # 3. Fuzzy match against already-collected canonicals
        for canonical in canonicals:
            if fuzzy_match(name, canonical):
                name_to_canonical[name] = canonical
                found = True
                break

        # 4. No match found — add as new canonical
        if not found:
            canonicals.append(name)
            name_to_canonical[name] = name

    return name_to_canonical
