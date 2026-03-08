from typing import List, Dict, Tuple
from shared.schemas import Person
from shared.utils.name_utils import build_canonical_map
import uuid
from shared.utils.email_utils import normalize_email

def resolve_people_ids(
    people_to_resolve: List[dict],
    people: List[Person],
    identities: Dict[str, List[str]],
) -> List[dict]:
    """
    Resolves each (name, email) pair to matching Person objects.
    Returns a list of result dicts, same length as people_to_resolve.
    Each result has: id, person, ambiguous.
    """
    canonical_map = build_canonical_map(people, identities)
    results = []
    for p in people_to_resolve:
        matches = resolve_person_id(p.get("name"), p.get("email"), people, canonical_map)
        if not matches:
            results.append({"id": p.get("id") or str(uuid.uuid4()), "person": None, "ambiguous": False})
        elif len(matches) == 1:
            results.append({"id": matches[0].id, "person": matches[0], "ambiguous": False})
        else:
            results.append({"id": ":".join(m.id for m in matches), "person": matches, "ambiguous": True})
    return results


def resolve_person_id(
    name: str | None,
    email: str | None,
    people: List[Person],
    canonical_map: Dict[str, str],
) -> List[Person]:
    """
    Returns matching Person objects for a given name/email.
    canonical_map should be pre-built via build_canonical_map().
    """
    if not name:
        return []

    canonical_name = canonical_map.get(name)
    if not canonical_name:
        return []

    matches = [p for p in people if canonical_map.get(p.name) == canonical_name]

    if len(matches) <= 1:
        return matches

    # Narrow by email if available
    if email:
        email_matches = [p for p in matches if normalize_email(p.email) == normalize_email(email)]
        if email_matches:
            return email_matches

    return matches