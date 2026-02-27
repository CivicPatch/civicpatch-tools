from typing import Dict, Set, List, Protocol
from nameparser import HumanName

def get_person_name(p):
    return p.get("name") if isinstance(p, dict) else p.name

class HasName(Protocol):
    """Protocol for objects with a name field."""
    name: str


def parse_name(name: str) -> HumanName:
    """Parse a name string into components."""
    return HumanName(name)


def exact_match(name1: str, name2: str) -> bool:
    """Exact name comparison (case-insensitive, whitespace-normalized)."""
    return name1.lower().strip() == name2.lower().strip()


def fuzzy_match(name1: str, name2: str) -> bool:
    """
    Looser name comparison using parsed name components.
    Matches if first + last name match, ignoring suffixes.
    """
    p1 = parse_name(name1)
    p2 = parse_name(name2)
    
    # Compare first and last names only (ignore suffix, middle, etc.)
    return (
        p1.first.lower() == p2.first.lower() and
        p1.last.lower() == p2.last.lower()
    )


def normalize_name(name: str) -> str:
    """Normalize name by removing suffixes and extra whitespace."""
    parsed = parse_name(name)
    # Reconstruct without suffix
    parts = [parsed.first, parsed.middle, parsed.last]
    return " ".join(p for p in parts if p).lower()

def build_canonical_map(
    all_people: List[dict],
    identities: Dict[str, List[str]]
) -> Dict[str, str]:
    """
    Map every name to its canonical form, using identities and fuzzy matching across all sources.
    """
    canonicals = []
    name_to_canonical = {}

    for person in all_people:
        name = get_person_name(person)
        found = False

        # 1. Identities-based matching
        if identities:
            for canonical, aliases in identities.items():
                if exact_match(name, canonical) or any(exact_match(name, alias) for alias in aliases):
                    name_to_canonical[name] = canonical
                    found = True
                    break
            if found:
                continue

            for canonical, aliases in identities.items():
                if fuzzy_match(name, canonical) or any(fuzzy_match(name, alias) for alias in aliases):
                    name_to_canonical[name] = canonical
                    found = True
                    break
            if found:
                continue

        # 2. Fuzzy match against already-collected canonicals
        for canonical in canonicals:
            if fuzzy_match(name, canonical):
                name_to_canonical[name] = canonical
                found = True
                break

        # 3. If still not found, add as new canonical
        if not found:
            canonicals.append(name)
            name_to_canonical[name] = name

    return name_to_canonical