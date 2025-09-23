

from typing import List, Dict, Tuple
from schemas import LLMPerson, PeopleByName, OtherNamesByCanonicalName
from nameparser import HumanName
from Levenshtein import distance as levenshtein_distance
from copy import deepcopy

NAME_SIMILARITY_THRESHOLD = 2


def normalize_name(name: str) -> str:
    """
    Normalize a name using nameparser to ensure consistent formatting.
    """
    parsed_name = HumanName(name)
    return f"{parsed_name.first} {parsed_name.last}".strip()

def first_name(name: str) -> str:
    """
    Extract the first name from a full name using nameparser.
    """
    parsed_name = HumanName(name)
    return parsed_name.first

def last_name(name: str) -> str:
    """
    Extract the last name from a full name using nameparser.
    """
    parsed_name = HumanName(name)
    return parsed_name.last

def has_name_overlap(record1: LLMPerson, record2: LLMPerson) -> bool:
    """
    Check if two records have overlapping first or last names.
    """
    parsed_name1 = HumanName(record1.name)
    parsed_name2 = HumanName(record2.name)
    firstname1 = parsed_name1.first
    firstname2 = parsed_name2.first
    surname1 = parsed_name1.last
    surname2 = parsed_name2.last

    return bool(set([firstname1, surname1]) & set([firstname2, surname2]))


def are_names_similar(first_name1: str, first_name2: str, threshold: int = NAME_SIMILARITY_THRESHOLD) -> bool:
    """
    Compare two first names using Levenshtein distance and determine if they are similar.
    """
    return levenshtein_distance(first_name1, first_name2) <= threshold


def find_canonical_name(normalized_name: str, people_by_name: PeopleByName) -> str:
    """
    Find the canonical name in people_by_name that matches the normalized name.
    Match by exact surname and similar first name.
    """
    parsed_normalized_name = HumanName(normalized_name)
    for existing_name in people_by_name.keys():
        parsed_existing_name = HumanName(existing_name)
        if parsed_existing_name.last == parsed_normalized_name.last:  # Exact surname match
            if are_names_similar(parsed_existing_name.first, parsed_normalized_name.first):
                return existing_name
    return normalized_name


def update_name_map(
    name_map: Dict[str, List[str]], canonical_name: str, original_name: str
) -> Dict[str, List[str]]:
    """
    Return an updated name_map with aliases for the canonical name.
    """
    updated_name_map = deepcopy(name_map)  # Create a deep copy to avoid side effects
    if canonical_name not in updated_name_map:
        updated_name_map[canonical_name] = []
    updated_name_map[canonical_name].append(original_name)
    return updated_name_map


def append_to_people_by_name(
    people_by_name: PeopleByName, canonical_name: str, people_list: List[LLMPerson]
) -> PeopleByName:
    """
    Return an updated people_by_name with the new people appended.
    """
    updated_people_by_name = people_by_name.copy()
    if canonical_name not in updated_people_by_name:
        updated_people_by_name[canonical_name] = []
    updated_people_by_name[canonical_name].extend(people_list)
    return updated_people_by_name


def group_people_by_name(
    names: OtherNamesByCanonicalName,
    people_by_name: PeopleByName,
    people_to_link: List[LLMPerson]
) -> Tuple[OtherNamesByCanonicalName, PeopleByName]:
    """
    Group people by their canonical names and update aliases.
    """
    name_map: OtherNamesByCanonicalName = {}
    linked_people = {}

    # Process people_to_link
    for person in people_to_link:
        normalized_name = normalize_name(person.name.strip())
        canonical_name = find_canonical_name(normalized_name, people_by_name)

        name_map = update_name_map(name_map, canonical_name, person.name.strip())

        if canonical_name not in linked_people:
            linked_people[canonical_name] = []
        linked_people[canonical_name].append(person)

    # Append linked_people to people_by_name
    for canonical_name, people_list in linked_people.items():
        people_by_name = append_to_people_by_name(people_by_name, canonical_name, people_list)

    # Process names dictionary for aliases
    for key, aliases in names.items():
        normalized_key = normalize_name(key)
        canonical_name = find_canonical_name(normalized_key, people_by_name)

        name_map = update_name_map(name_map, canonical_name, key)
        if canonical_name in name_map:
            name_map[canonical_name].extend(aliases)

    # Deduplicate and sort aliases in name_map for consistent order
    for canonical_name in name_map:
        name_map[canonical_name] = sorted(set(name_map[canonical_name]))

    return name_map, people_by_name

def is_weakly_tied(record1: LLMPerson, record2: LLMPerson) -> bool:
    """
    Determine if two records are weakly tied based on shared attributes.
    """

    if not has_name_overlap(record1, record2):
        return False

    # Check for matching roles
    if set(record1.roles) & set(record2.roles):
        return True

    # Check for matching email addresses
    if record1.email and record2.email and record1.email == record2.email: 
        return True

    # Check for matching websites if available
    if record1.website and record2.website and record1.website == record2.website:
        return True

    return False

