"""Grouping a page's records by name, against the names already known to be one person."""

import copy
import unicodedata
from typing import Dict, List, TypeAlias

from shared.schemas import PersonSourceRecord

PeopleByName: TypeAlias = Dict[str, List[PersonSourceRecord]]


def normalize_name(name: str) -> str:
    def remove_diacritics(text: str) -> str:
        # TODO: May want to do whitelist instead of blacklist
        return "".join(
            char
            for char in unicodedata.normalize("NFD", text)
            if unicodedata.category(char) != "Mn"
        )

    formatted_name = name.replace("‘", "'")
    formatted_name = remove_diacritics(formatted_name)
    # trim whitespace
    formatted_name = formatted_name.strip()
    return formatted_name


def group_people_by_name(
    known_mappings: Dict[str, List[str]],
    people_by_name: PeopleByName,
    people_to_link: List[PersonSourceRecord],
) -> Dict[str, List[PersonSourceRecord]]:
    """
    Group people by name, preserving known mappings and adding new people to the appropriate groups.
    """
    updated_people = copy.deepcopy(people_by_name)

    # Process people_to_link
    for person in people_to_link:
        normalized_name = normalize_name(person.name)
        matched = False
        for canonical_name, aliases in known_mappings.items():
            if normalized_name == normalize_name(canonical_name) or normalized_name in [
                normalize_name(alias) for alias in aliases
            ]:
                if canonical_name not in updated_people:
                    updated_people[canonical_name] = []
                updated_people[canonical_name].append(person)
                matched = True
                break
        if not matched:
            # If no match is found, add the person under their own name
            if person.name not in updated_people:
                updated_people[person.name] = []
            updated_people[person.name].append(person)

    return updated_people
