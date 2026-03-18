import re
from collections import Counter, defaultdict
from typing import List, Protocol, Dict, Set

from pydantic import BaseModel

from . import config_utils, name_utils


MIN_EXPECTED_PEOPLE = 3


class PersonLike(Protocol):
    name: str
    other_names: List[str] | None


class ReviewDecision(BaseModel):
    comment: str
    approved: bool


def get_identity_issues(
    research_people,
    people,
    identities: Dict[str, List[str]] | None = None,
) -> List[str]:
    identities = identities or {}
    canonical_map = name_utils.build_canonical_map(
        list(research_people) + list(people), identities
    )
    research_canonicals = {canonical_map[name_utils.get_person_name(p)] for p in research_people}
    people_canonicals = {canonical_map[name_utils.get_person_name(p)] for p in people}
    return _generate_issues(research_canonicals, people_canonicals)


def generate_review(
    research_people,
    people,
    identities: Dict[str, List[str]] | None = None,
):
    identities = identities or {}

    all_people = list(research_people) + list(people)
    canonical_map = name_utils.build_canonical_map(all_people, identities)

    research_canonicals = {canonical_map[name_utils.get_person_name(p)] for p in research_people}
    people_canonicals = {canonical_map[name_utils.get_person_name(p)] for p in people}

    all_canonicals = _collect_all_canonicals(research_canonicals, people_canonicals)
    issues = _generate_issues(research_canonicals, people_canonicals)
    issues.extend(_check_people_count(people))
    issues.extend(_check_unique_roles(people))
    issues.extend(_check_division_sequence(people))
    issues.extend(_check_office_name_sequence(people))
    rows = _generate_rows(all_canonicals, research_canonicals, people_canonicals)

    return {
        "issues": issues,
        "people_by_source": rows,
    }


def has_data_issues(people: List[dict]) -> bool:
    return bool(_check_people_count(people) or _check_division_sequence(people))


def get_data_issues(people: List[dict]) -> List[str]:
    return _check_people_count(people) + _check_division_sequence(people)


def generate_review_table_markdown(rows: List[Dict]) -> str:
    lines = [
        "| Canonical Name | In Research | In Data |",
        "|---------------|:-----------:|:-------:|",
    ]
    for row in rows:
        in_research = "✅" if row["in_research"] else "❌"
        in_data = "✅" if row["in_data"] else "❌"
        lines.append(f"| {row['name']} | {in_research} | {in_data} |")
    return "\n".join(lines)


# ── Identity / name comparison ────────────────────────────────────────────────

def _collect_all_canonicals(
    research_canonicals: Set[str],
    people_canonicals: Set[str],
) -> List[str]:
    return sorted(research_canonicals | people_canonicals)


def _generate_issues(
    research_canonicals: Set[str],
    people_canonicals: Set[str],
) -> List[str]:
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
    return [
        _build_row(name, research_canonicals, people_canonicals)
        for name in all_canonicals
    ]


def _build_row(
    name: str,
    research_canonicals: Set[str],
    people_canonicals: Set[str],
) -> Dict:
    return {
        "name": name,
        "in_research": name in research_canonicals,
        "in_data": name in people_canonicals,
    }


# ── People count ──────────────────────────────────────────────────────────────

def _check_people_count(people) -> List[str]:
    if len(people) < MIN_EXPECTED_PEOPLE:
        return [f"Only {len(people)} people found (minimum expected: {MIN_EXPECTED_PEOPLE})"]
    return []


# ── Unique roles ──────────────────────────────────────────────────────────────

def _get_office_name(person) -> str:
    if isinstance(person, dict):
        return (person.get("office") or {}).get("name") or ""
    return getattr(getattr(person, "office", None), "name", "") or ""


def _check_unique_roles(people) -> List[str]:
    unique_roles = {r.lower() for r in config_utils.get_unique_roles()}
    role_to_persons = defaultdict(list)
    for person in people:
        tokens = [t.strip() for t in _get_office_name(person).lower().split(" - ") if t.strip()]
        for token in tokens:
            if token in unique_roles:
                role_to_persons[token].append(name_utils.get_person_name(person))
    return [
        f"Role '{role}' is marked as unique but found in multiple officials: {', '.join(persons)}"
        for role, persons in role_to_persons.items()
        if len(persons) > 1
    ]


# ── Division sequence ─────────────────────────────────────────────────────────

def _get_division_ocdid(person) -> str:
    if isinstance(person, dict):
        return (person.get("office") or {}).get("division_ocdid") or ""
    office = getattr(person, "office", None)
    return (office.division_ocdid or "") if office else ""


def _parse_division_entries(people) -> List[tuple]:
    entries = []
    for p in people:
        match = re.search(r"/([^/:]+):(\d+)$", _get_division_ocdid(p))
        if match:
            entries.append((match.group(1).replace("_", " "), int(match.group(2))))
    return entries


def _missing_division_issues(label: str, numbers: List[int]) -> List[str]:
    expected = set(range(min(numbers), max(numbers) + 1))
    return [
        f"Missing official with {label} {n}"
        for n in sorted(expected - set(numbers))
    ]


def _inconsistent_count_issues(label: str, numbers: List[int]) -> List[str]:
    counts = Counter(numbers)
    expected_count = Counter(counts.values()).most_common(1)[0][0]
    return [
        f"{label.title()} {n} has {c} official(s) (expected {expected_count})"
        for n, c in sorted(counts.items())
        if c != expected_count
    ]


def _parse_office_name_entries(people) -> List[tuple]:
    entries = []
    for p in people:
        for part in _get_office_name(p).split(" - "):
            match = re.search(r"^(.+?)\s+(\d+)$", part.strip(), re.IGNORECASE)
            if match:
                entries.append((match.group(1).strip().lower(), int(match.group(2))))
    return entries


def _check_numeric_sequence(entries: List[tuple]) -> List[str]:
    if not entries:
        return []
    label = entries[0][0]
    numbers = [n for _, n in entries]
    return _missing_division_issues(label, numbers) + _inconsistent_count_issues(label, numbers)


def _check_division_sequence(people) -> List[str]:
    return _check_numeric_sequence(_parse_division_entries(people))


def _check_office_name_sequence(people) -> List[str]:
    return _check_numeric_sequence(_parse_office_name_entries(people))
