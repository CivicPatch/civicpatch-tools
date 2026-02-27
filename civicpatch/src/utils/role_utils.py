from typing import List, Any

def people_with_roles(people: List[Any], roles: List[str]):
    # Accepts dicts or objects (like Pydantic models)
    result = []
    for p in people:
        # Get role(s) from object or dict
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
        # Check if any of person's roles are in the roles list
        if any(r.lower() in roles for r in person_roles):
            result.append(p)
    return result