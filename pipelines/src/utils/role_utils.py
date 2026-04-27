from typing import Dict, List, Any, Optional
from rapidfuzz import fuzz, process


def fuzzy_match_role(role: str, role_aliases: Dict[str, str]) -> Optional[str]:
    prenorm = lambda s: s.replace('-', ' ').lower()
    candidates = {prenorm(k): v for k, v in role_aliases.items()}
    result = process.extractOne(
        prenorm(role), candidates.keys(), scorer=fuzz.ratio, score_cutoff=85
    )
    if result is None:
        return None
    return candidates[result[0]]


def people_with_roles(people: List[Any], roles: List[str]):
    # Accepts dicts or objects (like Pydantic models)
    result = []
    for p in people:
        person_roles = []
        if hasattr(p, "roles") and getattr(p, "roles") is not None:
            person_roles = getattr(p, "roles")
        elif hasattr(p, "role") and getattr(p, "role") is not None:
            person_roles = [getattr(p, "role")]
        elif isinstance(p, dict):
            if "roles" in p and p["roles"] is not None:
                person_roles = p["roles"]
            elif "role" in p and p["role"] is not None:
                person_roles = [p["role"]]
        if any(r.lower() in roles for r in person_roles):
            result.append(p)
    return result
