import uuid
from typing import Dict, List, Tuple

from shared.schemas import Person
from shared.utils.email_utils import normalize_email
from shared.utils.name_utils import best_identity_match, build_canonical_map


def resolve_people_ids(
    people_to_resolve: List[dict],
    people: List[Person],
    identities: Dict[str, List[str]],
) -> List[dict]:
    canonical_map = build_canonical_map(people, identities)
    results = []
    for p in people_to_resolve:
        matches = resolve_person_id(
            p.get("name"), p.get("email"), people, canonical_map, identities
        )
        if not matches:
            results.append(
                {
                    "id": p.get("id") or str(uuid.uuid4()),
                    "person": None,
                    "ambiguous": False,
                }
            )
        elif len(matches) == 1:
            results.append(
                {"id": matches[0].id, "person": matches[0], "ambiguous": False}
            )
        else:
            results.append(
                {
                    "id": ":".join(m.id for m in matches),
                    "person": matches,
                    "ambiguous": True,
                }
            )
    return results


def ensure_person_ids(people: List[dict]) -> List[dict]:
    return [{**person, "id": person.get("id") or str(uuid.uuid4())} for person in people]


def resolve_person_id(
    name: str | None,
    email: str | None,
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
    if email:
        email_matches = [
            p for p in matches if normalize_email(p.email) == normalize_email(email)
        ]
        if email_matches:
            return email_matches
    return matches
