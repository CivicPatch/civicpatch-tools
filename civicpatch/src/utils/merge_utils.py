from typing import List, Dict, Tuple
from schemas import LLMPerson, Person, PeopleByName, OtherNamesByCanonicalName
from nameparser import HumanName
from Levenshtein import distance as levenshtein_distance
from copy import deepcopy
import unicodedata

NAME_SIMILARITY_THRESHOLD = 2

def normalize_name(name: str) -> str:
    """
    Normalize a name using nameparser to ensure consistent formatting.
    """
    formatted_name = name.replace('‘', "'")
    formatted_name = remove_diacritics(formatted_name)
    return formatted_name

def remove_diacritics(text: str) -> str:
    """
    Normalize a string by removing diacritics (accents).
    """
    # TODO: May want to do whitelist instead of blacklist
    return ''.join(
        char for char in unicodedata.normalize('NFD', text)
        if unicodedata.category(char) != 'Mn'
    )

def same_name(record1: LLMPerson, record2: LLMPerson) -> bool:
    """
    Check if two records have the same normalized name.
    """

    return (
        first_name(record1.name) == first_name(record2.name)) & (
            last_name(record1.name) == last_name(record2.name)
        )

def first_name(name: str) -> str:
    """
    Extract the first name from a full name using nameparser.
    """
    formatted_name = normalize_name(name)
    human_name = HumanName(formatted_name)
    return human_name.first

def last_name(name: str) -> str:
    """
    Extract the last name from a full name using nameparser.
    """
    formatted_name = normalize_name(name)
    human_name = HumanName(formatted_name)
    return human_name.last

def has_name_overlap(name1: str, name2: str) -> bool:
    """
    Check if two records have the same last names.
    """
    return last_name(name1) == last_name(name2)


def are_names_similar(name1: str, name2: str, threshold: int = NAME_SIMILARITY_THRESHOLD) -> bool:
    """
    Compare two first names using Levenshtein distance and determine if they are similar.
    """
    normalized_first_name1 = first_name(name1)
    normalized_first_name2 = first_name(name2)
    return levenshtein_distance(normalized_first_name1, normalized_first_name2) <= threshold

def find_indexed_name(normalized_name: str, people_by_name: PeopleByName) -> str:
    """
    Find the canonical name in people_by_name that matches the normalized name.
    Match by exact surname and similar first name.
    """
    for existing_name in people_by_name.keys():
        if has_name_overlap(normalized_name, existing_name): # Exact surname match
            if are_names_similar(existing_name, normalized_name):
                return existing_name
    return normalized_name


def update_name_map(
    name_map: Dict[str, List[str]], indexed_name: str, original_name: str
) -> Dict[str, List[str]]:
    """
    Return an updated name_map with aliases for the canonical name.
    """
    updated_name_map = deepcopy(name_map)  # Create a deep copy to avoid side effects
    if indexed_name not in updated_name_map:
        updated_name_map[indexed_name] = []
    updated_name_map[indexed_name].append(original_name)
    return updated_name_map


def append_to_people_by_name(
    people_by_name: PeopleByName, indexed_name: str, people_list: List[LLMPerson]
) -> PeopleByName:
    """
    Return an updated people_by_name with the new people appended.
    """
    updated_people_by_name = people_by_name.copy()
    if indexed_name not in updated_people_by_name:
        updated_people_by_name[indexed_name] = []
    updated_people_by_name[indexed_name].extend(people_list)
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
        indexed_name = find_indexed_name(normalized_name, people_by_name)

        name_map = update_name_map(name_map, indexed_name, person.name.strip())

        if indexed_name not in linked_people:
            linked_people[indexed_name] = []
        linked_people[indexed_name].append(person)

    # Append linked_people to people_by_name
    for indexed_name, people_list in linked_people.items():
        people_by_name = append_to_people_by_name(people_by_name, indexed_name, people_list)

    # Process names dictionary for aliases
    for key, aliases in names.items():
        normalized_key = normalize_name(key)
        indexed_name = find_indexed_name(normalized_key, people_by_name)

        name_map = update_name_map(name_map, indexed_name, key)
        if indexed_name in name_map:
            name_map[indexed_name].extend(aliases)

    # Deduplicate and sort aliases in name_map for consistent order
    for indexed_name in name_map:
        name_map[indexed_name] = sorted(set(name_map[indexed_name]))

    return name_map, people_by_name

def is_weakly_tied(record1: LLMPerson|Person, record2: LLMPerson|Person) -> bool:
    """
    Determine if two records are weakly tied based on shared attributes.
    """

    if not has_name_overlap(record1.name, record2.name):
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

