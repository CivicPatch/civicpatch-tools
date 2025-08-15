#from schemas import People
from typing import List
from schemas import OtherNamesByCanonicalName

def filter_people_by_roles(role_configs, people):
    """
    Filters people whose 'role' matches any role or alias in role_configs.
    Args:
        role_configs: List of dicts, each with 'role' and optional 'aliases'.
        people: List of dicts, each with a 'role' key.
    Returns:
        List of people whose role matches.
    """
    # Build a set of all valid role names and aliases (lowercased)
    valid_roles = set()
    for role_entry in role_configs:
        valid_roles.add(role_entry["role"].strip().lower())
        for alias in role_entry.get("aliases", []):
            valid_roles.add(alias.strip().lower())

    # Filter people whose role matches any vigalid role/alias
    filtered = []
    for person in people:
        person_roles = [r.strip().lower() for r in person.get("roles", [])]
        if any(role in valid_roles for role in person_roles):
            filtered.append(person)

    return filtered

