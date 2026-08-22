import uuid
from typing import Dict, List

from shared.schemas import Person
from shared.utils.email_utils import normalize_email
from shared.utils.name_utils import best_identity_match, build_canonical_map


def _unmatched(person: dict, duplicate_match: bool = False) -> dict:
    return {
        "id": person.get("id") or str(uuid.uuid4()),
        "person": None,
        "ambiguous": False,
        "duplicate_match": duplicate_match,
    }


def _resolution(person: dict, matches: List[Person], claimed_ids: set) -> dict:
    if not matches:
        return _unmatched(person)
    if len(matches) > 1:
        return {
            "id": ":".join(m.id for m in matches),
            "person": matches,
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
        return _unmatched(person, duplicate_match=True)
    return {
        "id": matches[0].id,
        "person": matches[0],
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
            p.get("name"), p.get("emails") or [], people, canonical_map, identities
        )
        result = _resolution(p, matches, claimed_ids)
        claimed_ids.add(result["id"])
        results.append(result)
    return results


def ensure_person_ids(people: List[dict]) -> List[dict]:
    return [{**person, "id": person.get("id") or str(uuid.uuid4())} for person in people]


def resolve_person_id(
    name: str | None,
    emails: List[str],
    people: List[Person],
    canonical_map: Dict[str, str],
    identities: Dict[str, List[str]],
) -> List[Person]:
    if not name:
        return []
    canonical_name = canonical_map.get(name)
    if not canonical_name:
        canonical_name = best_identity_match(name, identities)
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
            return email_matches
    return matches


def merge_forward_other_names(
    person_name: str,
    person_other_names: List[str],
    existing_name: str | None,
    existing_other_names: List[str],
) -> List[str]:
    """Carry the matched entity's confirmed aliases forward onto the freshly-scraped
    person, so human-added `other_names` survive every run — they are the durable
    signal that steers the next run's name matching. If the entity was renamed, both
    the old and new names become aliases too. Deduped, order-preserving.

    Load-bearing: drop the existing-aliases merge and each run clobbers human aliases.
    """
    # A renamed entity keeps both names as aliases; existing aliases always carry forward.
    renamed_variants = (
        [person_name, existing_name]
        if existing_name and existing_name != person_name
        else []
    )
    existing_aliases = [n for n in existing_other_names if isinstance(n, str)]
    return list(dict.fromkeys(person_other_names + renamed_variants + existing_aliases))
