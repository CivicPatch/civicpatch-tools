import re
from collections import defaultdict
from typing import Dict, List, Protocol, Set

from pydantic import BaseModel
from shared.schemas import POST_FIELD, Issue, IssueCode

from . import name_utils


class ReviewInputs(BaseModel):
    identities: Dict[str, List[str]] = {}
    unique_roles: List[str] = []


MIN_EXPECTED_PEOPLE = 3


class PersonLike(Protocol):
    name: str
    other_names: List[str] | None


class ReviewDecision(BaseModel):
    comment: str
    approved: bool


def markdown_url_list(items: List[str]) -> str:
    """Render a list of URLs as GitHub-flavoured markdown links separated by <br>."""
    if not items:
        return "N/A"
    return "<br>".join(f"[{item}]({item})" for item in items)


def markdown_identities(identities: Dict[str, List[str]]) -> str:
    """Render an identities dict (canonical → aliases) as a <br>-separated list."""
    if not identities:
        return "N/A"
    return "<br>".join(
        f"{canonical}: {', '.join(aliases)}"
        for canonical, aliases in identities.items()
    )


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


def _get_role(person) -> str:
    """The role the labels parsed to, which is the only thing comparable to a role name.

    Not `labels`: those are the source's own words, and a scraped label carries its division
    ("Council President Ward 9"), so matching them against role names finds nothing.
    """
    if isinstance(person, dict):
        return person.get("role_id") or ""
    return getattr(person, "role_id", None) or ""


def _get_division_ocdid(person) -> str:
    if isinstance(person, dict):
        return person.get("division_ocdid") or ""
    return getattr(person, "division_ocdid", None) or ""


def _parse_division_entries(people) -> List[tuple]:
    entries = []
    for p in people:
        match = re.search(r"/([^/:]+):(\d+)$", _get_division_ocdid(p))
        if match:
            entries.append((match.group(1).replace("_", " "), int(match.group(2))))
    return entries


def _get_person_id(person) -> str:
    return person.get("id", "")


def _check_absent_people(
    research_canonicals: Set[str], people_canonicals: Set[str]
) -> List[Issue]:
    return [
        Issue(
            code=IssueCode.ABSENT_PERSON,
            message=f"Not found in this scrape: {name}",
            person_ids=[],
        )
        for name in sorted(research_canonicals - people_canonicals)
    ]


def _check_new_people(
    people, canonical_map: Dict[str, str], research_canonicals: Set[str]
) -> List[Issue]:
    issues = []
    for person in people:
        if canonical_map[name_utils.get_person_name(person)] in research_canonicals:
            continue
        person_id = _get_person_id(person)
        issues.append(
            Issue(
                code=IssueCode.NEW_PERSON,
                message=f"New person found: {name_utils.get_person_name(person)}",
                person_ids=[person_id] if person_id else [],
            )
        )
    return issues


def _check_too_few_people(people) -> List[Issue]:
    if len(people) >= MIN_EXPECTED_PEOPLE:
        return []
    message = (
        f"Only {len(people)} people found (minimum expected: {MIN_EXPECTED_PEOPLE})"
    )
    return [Issue(code=IssueCode.TOO_FEW_PEOPLE, message=message, person_ids=[])]


def _check_duplicate_unique_roles(people, unique_roles: List[str]) -> List[Issue]:
    unique_roles_set = {r.lower() for r in unique_roles}
    role_to_holders = defaultdict(list)  # role -> [(id, name), ...]
    for person in people:
        role = _get_role(person).lower().strip()
        if role in unique_roles_set:
            role_to_holders[role].append(
                (_get_person_id(person), name_utils.get_person_name(person))
            )
    return [
        Issue(
            code=IssueCode.DUPLICATE_UNIQUE_ROLE,
            message=f"Role '{role}' is marked as unique but found in multiple officials: {', '.join(name for _, name in holders)}",
            person_ids=[pid for pid, _ in holders if pid],
            field=POST_FIELD,
        )
        for role, holders in role_to_holders.items()
        if len(holders) > 1
    ]


def _check_division_numbering(people) -> List[Issue]:
    entries = _parse_division_entries(people)
    if not entries:
        return []
    label = entries[0][0]
    numbers = {n for _, n in entries}
    expected = set(range(min(numbers), max(numbers) + 1))
    return [
        Issue(
            code=IssueCode.DIVISION_NUMBERING_GAP,
            message=f"Missing {label} {n}",
            person_ids=[],
        )
        for n in sorted(expected - numbers)
    ]


def build_review_summary(
    research_people,
    people,
    inputs: ReviewInputs | None = None,
    origin_source: str = "google_gemini",
) -> dict:
    inputs = inputs or ReviewInputs()
    # Normalize to dicts once so every check reads fields uniformly (the pipeline passes
    # Official objects, open-data passes yaml dicts).
    people = [p if isinstance(p, dict) else p.model_dump() for p in people]
    research_people = [
        p if isinstance(p, dict) else p.model_dump() for p in research_people
    ]

    all_people = list(research_people) + list(people)
    canonical_map = name_utils.build_canonical_map(all_people, inputs.identities)
    research_canonicals = {
        canonical_map[name_utils.get_person_name(p)] for p in research_people
    }
    people_canonicals = {canonical_map[name_utils.get_person_name(p)] for p in people}

    issues: List[Issue] = [
        *_check_absent_people(research_canonicals, people_canonicals),
        *_check_new_people(people, canonical_map, research_canonicals),
        *_check_too_few_people(people),
        *_check_duplicate_unique_roles(people, inputs.unique_roles),
        *_check_division_numbering(people),
    ]

    all_canonicals = _collect_all_canonicals(research_canonicals, people_canonicals)
    rows = _generate_rows(all_canonicals, research_canonicals, people_canonicals)
    return {"issues": issues, "people_by_source": rows, "origin_source": origin_source}
