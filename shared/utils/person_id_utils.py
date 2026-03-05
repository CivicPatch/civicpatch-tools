from typing import List, Dict
from shared.schemas import Person
from shared.utils.name_utils import build_canonical_map

def resolve_person_id(
        name: str, 
        email: str, 
        people: List[Person], 
        identities: Dict[str, List[str]]
    ) -> List[Person]:
    """
    Given a name, email, people list, and identities mapping,
    return a list of matching people (dicts) if ambiguous, or a single match if unique.
    """
    canonical_map = build_canonical_map(people, identities)
    canonical_name = canonical_map.get(name)
    # Find all people with matching canonical name
    matches = [p for p in people if canonical_map.get(p.name) == canonical_name]
    # If only one match, return its id
    if len(matches) == 1:
        return [matches[0]]
    # If multiple, filter by email if possible
    email_matches = [p for p in matches if p.email == email]
    if len(email_matches) == 1:
        return [email_matches[0]]
    elif email_matches:
        return email_matches
    # If still ambiguous, return all name matches
    return matches