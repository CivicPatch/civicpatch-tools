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
    return name1.lower().strip() == name2.lower().strip()


def _normalize_suffix(suffix: str) -> str:
    """Normalize suffix for comparison (e.g. 'Jr.' -> 'jr', 'Jr' -> 'jr')."""
    return suffix.lower().strip().rstrip(".")


def fuzzy_match(name1: str, name2: str) -> bool:
    p1 = parse_name(name1)
    p2 = parse_name(name2)

    if p1.first.lower() != p2.first.lower() or p1.last.lower() != p2.last.lower():
        return False
    if p1.middle and p2.middle and p1.middle.lower() != p2.middle.lower():
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
    if p1.first.lower() == p2.first.lower():
        score += 1
    if p1.last.lower() == p2.last.lower():
        score += 1
    if p1.middle and p2.middle and p1.middle.lower() == p2.middle.lower():
        score += 1
    if (
        p1.suffix
        and p2.suffix
        and _normalize_suffix(p1.suffix) == _normalize_suffix(p2.suffix)
    ):
        score += 1
    return score


def normalize_name(name: str) -> str:
    """Normalize name by removing accents, titles, suffixes, and extra whitespace, but preserving nickname."""
    hn = HumanName(name)
    parts = [hn.first, hn.middle, hn.last]
    if hn.nickname:
        parts.append(f'"{hn.nickname}"')
    base = " ".join(p for p in parts if p)
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    return base.lower().strip()


def best_identity_match(name: str, identities: Dict[str, List[str]]) -> str | None:
    best_canonical = None
    best_score = 0
    for canonical, aliases in identities.items():
        for candidate in [canonical] + aliases:
            if fuzzy_match(name, candidate):
                score = _fuzzy_match_score(name, candidate)
                print(f"  {name!r} vs {candidate!r} → score={score}")
                if score > best_score:
                    best_score = score
                    best_canonical = canonical
    print(f"  best for {name!r}: {best_canonical!r} (score={best_score})")
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
