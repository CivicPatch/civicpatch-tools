import uuid
from typing import Dict, List

from shared.schemas import Person
from shared.utils.email_utils import normalize_email
from shared.utils.name_utils import (
    best_identity_match,
    build_canonical_map,
    exact_identity_match,
    fuzzy_match_score,
    nickname_tie,
    same_name,
    same_surname,
)


def _new_identity(person: dict, duplicate_match: bool = False) -> dict:
    """Nobody to match, so they get an id of their own.

    Not `_unmatched`: `unmatched` next door means residue *inside a label* that resolved to no
    role, and the two have nothing to do with each other.
    """
    return {
        "id": person.get("id") or str(uuid.uuid4()),
        "person": None,
        "matches": [],
        "ambiguous": False,
        "duplicate_match": duplicate_match,
    }


def _resolution(person: dict, matches: List[Person], claimed_ids: set) -> dict:
    if not matches:
        return _new_identity(person)
    if len(matches) > 1:
        if matches[0].id in claimed_ids:
            return _new_identity(person, duplicate_match=True)
        return {
            "id": matches[0].id,
            "person": matches[0],
            "matches": matches,
            "ambiguous": True,
            "duplicate_match": False,
        }
    # Two entries resolving to one existing person means the source listed an
    # official twice, or one of them matched wrongly. Handing out the id again
    # would be worse than either: every consumer keys people by id, so the pair
    # collapses into a single record and one person's data is dropped without
    # ever being shown. The later entry keeps an identity of its own instead,
    # which surfaces it as a new person for a reviewer to judge.
    if matches[0].id in claimed_ids:
        return _new_identity(person, duplicate_match=True)
    return {
        "id": matches[0].id,
        "person": matches[0],
        "matches": matches,
        "ambiguous": False,
        "duplicate_match": False,
    }


def resolve_people_ids(
    people_to_resolve: List[dict],
    people: List[Person],
    identities: Dict[str, List[str]],
) -> List[dict]:
    canonical_map = build_canonical_map(people, identities)
    results = []
    claimed_ids: set[str] = set()
    for p in people_to_resolve:
        matches = resolve_person_id(
            p.get("name"),
            p.get("other_names") or [],
            p.get("emails") or [],
            people,
            canonical_map,
            identities,
        )
        result = _resolution(p, matches, claimed_ids)
        claimed_ids.add(result["id"])
        results.append(result)

    unmatched = {
        index: person.get("name") or ""
        for index, (person, result) in enumerate(zip(people_to_resolve, results))
        if result["person"] is None and not result["duplicate_match"]
    }
    ties = _nickname_ties(unmatched, _absent(people, claimed_ids))
    return [
        _resolution(people_to_resolve[index], [ties[index]], set()) if index in ties else result
        for index, result in enumerate(results)
    ]


def _absent(people: List[Person], claimed_ids: set[str]) -> List[Person]:
    """Published people still on the roster whom no entry matched."""
    return [person for person in people if person.id not in claimed_ids and person.memberships]


def _nickname_ties(unmatched: Dict[int, str], absent: List[Person]) -> Dict[int, Person]:
    """An unmatched entry and an absent person, when they are the only two sharing a surname
    and their first names are a nickname pair: one leaves, one arrives, "Dave" for "David"."""
    ties = {}
    for index, name in unmatched.items():
        same_surname_absent = [person for person in absent if same_surname(name, person.name)]
        if len(same_surname_absent) != 1:
            continue
        candidate = same_surname_absent[0]
        same_surname_new = [other for other in unmatched.values() if same_surname(other, candidate.name)]
        if len(same_surname_new) == 1 and nickname_tie(name, candidate.name):
            ties[index] = candidate
    return ties


def ensure_person_ids(people: List[dict]) -> List[dict]:
    return [
        {**person, "id": person.get("id") or str(uuid.uuid4())} for person in people
    ]


def _canonical_for(
    name: str,
    other_names: List[str],
    canonical_map: Dict[str, str],
    identities: Dict[str, List[str]],
) -> str | None:
    """The name as published, then a name the source stated outright, then a guess."""
    if canonical_map.get(name):
        return canonical_map[name]
    for other_name in other_names:
        stated = exact_identity_match(other_name, identities)
        if stated is not None:
            return stated
    return best_identity_match(name, identities)


def resolve_person_id(
    name: str | None,
    other_names: List[str],
    emails: List[str],
    people: List[Person],
    canonical_map: Dict[str, str],
    identities: Dict[str, List[str]],
) -> List[Person]:
    if not name:
        return []
    canonical_name = _canonical_for(name, other_names, canonical_map, identities)
    if not canonical_name:
        return []
    matches = [p for p in people if canonical_map.get(p.name) == canonical_name]
    if len(matches) <= 1:
        return matches
    wanted = {normalize_email(email) for email in emails if email}
    if wanted:
        email_matches = [
            p
            for p in matches
            if wanted & {normalize_email(email) for email in p.emails if email}
        ]
        if email_matches:
            matches = email_matches
    # Likeliest first, so a caller narrowing to one can take the head. Every candidate already
    # shares a canonical name, so this only separates them on the components the canonical form
    # threw away — a middle name, a suffix.
    #
    # `id` last because the sort must be total on its own: callers pass `people` from wherever,
    # and leaning on their ordering would make this depend on an `ORDER BY` in another package.
    return sorted(
        matches, key=lambda person: (-fuzzy_match_score(name, person.name), person.id)
    )


def merge_forward_other_names(
    person_name: str,
    person_other_names: List[str],
    existing_name: str | None,
    existing_other_names: List[str],
) -> List[str]:
    renamed = bool(existing_name) and not same_name(existing_name or "", person_name)
    renamed_variants = [person_name, existing_name] if renamed else []
    existing_aliases = [n for n in existing_other_names if isinstance(n, str)]

    merged: List[str] = []
    for name in person_other_names + renamed_variants + existing_aliases:
        # Only a rename earns the current name a place among its own aliases.
        if not renamed and same_name(name, person_name):
            continue
        if any(same_name(name, kept) for kept in merged):
            continue
        merged.append(name)
    return merged
