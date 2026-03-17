import re
from typing import List, Protocol, Dict, Set
from . import name_utils

MIN_EXPECTED_PEOPLE = 3

class PersonLike(Protocol):
    """Protocol for objects with name and other_names fields."""
    name: str
    other_names: List[str] | None

def generate_review(
    research_people: List[dict],
    people: List[dict],
    identities: Dict[str, List[str]] | None = None,
):
    identities = identities or {}

    # 1. Gather all people
    all_people = []
    all_people.extend(research_people)
    all_people.extend(people)

    # 2. Build canonical map
    canonical_map = name_utils.build_canonical_map(all_people, identities)

    # 3. Build canonical sets for each source
    research_canonicals = {canonical_map[name_utils.get_person_name(p)] for p in research_people}
    people_canonicals = {canonical_map[name_utils.get_person_name(p)] for p in people}

    all_canonicals = _collect_all_canonicals(research_canonicals, people_canonicals)
    issues = _generate_issues(research_canonicals, people_canonicals)
    issues.extend(_check_people_count(people))
    issues.extend(_check_division_sequence(people))
    rows = _generate_rows(all_canonicals, research_canonicals, people_canonicals)

    return {
        "issues": issues,
        "people_by_source": rows,
    }

def _collect_all_canonicals(
    research_canonicals: Set[str],
    people_canonicals: Set[str],
) -> List[str]:
    """Collect and sort all canonical names from all sources."""
    all_names = research_canonicals | people_canonicals
    return sorted(all_names)

def _generate_issues(
    research_canonicals: Set[str],
    people_canonicals: Set[str],
) -> List[str]:
    """Generate issue strings for mismatches between research and final."""
    issues = []

    for name in sorted(people_canonicals - research_canonicals):
        issues.append(f"Extra official: {name}")

    for name in sorted(research_canonicals - people_canonicals):
        issues.append(f"Missing official: {name}")

    return issues

def _generate_rows(
    all_canonicals: List[str],
    research_canonicals: Set[str],
    people_canonicals: Set[str],
) -> List[Dict]:
    """Generate table rows for each canonical name."""
    return [
        _build_row(name, research_canonicals, people_canonicals)
        for name in all_canonicals
    ]

def _build_row(
    name: str,
    research_canonicals: Set[str],
    people_canonicals: Set[str],
) -> Dict:
    """Build a single row dict for a canonical name."""
    return {
        "name": name,
        "in_research": name in research_canonicals,
        "in_data": name in people_canonicals,
    }

def has_data_issues(people: List[dict]) -> bool:
    return bool(_check_people_count(people) or _check_division_sequence(people))

def get_data_issues(people: List[dict]) -> List[str]:
    return _check_people_count(people) + _check_division_sequence(people)

def _check_people_count(people: List[dict]) -> List[str]:
    if len(people) < MIN_EXPECTED_PEOPLE:
        return [f"Only {len(people)} people found (minimum expected: {MIN_EXPECTED_PEOPLE})"]
    return []

def _check_division_sequence(people: List[dict]) -> List[str]:
    numbers = []
    for p in people:
        ocdid = (p.get("office") or {}).get("division_ocdid") or ""
        match = re.search(r":(\d+)$", ocdid)
        if match:
            numbers.append(int(match.group(1)))

    if not numbers:
        return []

    expected = list(range(min(numbers), max(numbers) + 1))
    if sorted(numbers) != expected:
        return [f"Division number sequence is irregular: {sorted(numbers)} (expected {expected})"]
    return []