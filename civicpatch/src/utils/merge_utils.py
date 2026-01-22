from typing import List, Dict, Tuple
from domain.models import Person
from jobs.people_collector.schemas import LLMPerson, PeopleByName, OtherNamesByCanonicalName, PeopleCollectorContext
from nameparser import HumanName
from Levenshtein import distance as levenshtein_distance
from copy import deepcopy
import unicodedata

NAME_SIMILARITY_THRESHOLD = 2

def normalize_name(name: str) -> str:
    """
    Normalize a name using nameparser to ensure consistent formatting.
    """
    def remove_diacritics(text: str) -> str:
        # TODO: May want to do whitelist instead of blacklist
        return ''.join(
            char for char in unicodedata.normalize('NFD', text)
            if unicodedata.category(char) != 'Mn'
        )

    formatted_name = name.replace('‘', "'")
    formatted_name = remove_diacritics(formatted_name)
    # trim whitespace
    formatted_name = formatted_name.strip()
    return formatted_name

def same_name(name1: str, name2: str) -> bool:
    """
    Check if two records have the same normalized name.
    """

    return (
        first_name(name1) == first_name(name2)
    ) & (
        last_name(name1) == last_name(name2)
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
    return last_name(name1) == last_name(name2) or first_name(name1) == first_name(name2)


def are_names_similar(name1: str, name2: str, threshold: int = NAME_SIMILARITY_THRESHOLD) -> bool:
    """
    Compare two first names using Levenshtein distance and determine if they are similar.
    """
    normalized_first_name1 = first_name(name1)
    normalized_first_name2 = first_name(name2)
    return levenshtein_distance(normalized_first_name1, normalized_first_name2) <= threshold

def resolve_from_known_mappings(name: str, known_mappings: OtherNamesByCanonicalName) -> str:
    """
    Check if a name has a canonical form in known mappings (config + runtime).
    Returns canonical name or original name if no match.
    """
    if not known_mappings:
        return name
        
    normalized_input = normalize_name(name.strip()).lower()
    
    # Check if it's already a canonical name
    for canonical in known_mappings.keys():
        if normalize_name(canonical).lower() == normalized_input:
            return canonical
    
    # Check if it's an alias for a canonical name
    for canonical, aliases in known_mappings.items():
        for alias in aliases:
            if normalize_name(alias).lower() == normalized_input:
                return canonical
    
    return name

def find_indexed_name(normalized_name: str, people_by_name: PeopleByName, known_mappings: OtherNamesByCanonicalName = None) -> str:
    """
    Find the canonical name that matches the normalized name.
    Priority: 1) Known mappings (config + runtime), 2) Similarity matching
    """
    # Priority 1: Check known mappings (includes both config and runtime discoveries)
    if known_mappings:
        canonical = resolve_from_known_mappings(normalized_name, known_mappings)
        if canonical != normalized_name:
            return canonical
    
    # Priority 2: Existing similarity-based matching
    for existing_name in people_by_name.keys():
        if has_name_overlap(normalized_name, existing_name):
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
    known_mappings: OtherNamesByCanonicalName,  # Renamed: this is your merged names
    people_by_name: PeopleByName,
    people_to_link: List[LLMPerson]
) -> Tuple[OtherNamesByCanonicalName, PeopleByName]:
    """
    Group people by their canonical names and update mappings.
    known_mappings contains both config and previously discovered name mappings.
    """
    updated_mappings: OtherNamesByCanonicalName = {}
    linked_people = {}

    # Process people_to_link
    for person in people_to_link:
        normalized_name = normalize_name(person.name)
        indexed_name = find_indexed_name(normalized_name, people_by_name, known_mappings)

        updated_mappings = update_name_map(updated_mappings, indexed_name, normalized_name)

        if indexed_name not in linked_people:
            linked_people[indexed_name] = []
        linked_people[indexed_name].append(person)

    # Append linked_people to people_by_name
    for indexed_name, people_list in linked_people.items():
        people_by_name = append_to_people_by_name(people_by_name, indexed_name, people_list)

    # Process known mappings to ensure they're preserved
    for canonical, aliases in known_mappings.items():
        normalized_canonical = normalize_name(canonical)
        indexed_name = find_indexed_name(normalized_canonical, people_by_name, known_mappings)

        updated_mappings = update_name_map(updated_mappings, indexed_name, canonical)
        if indexed_name in updated_mappings:
            updated_mappings[indexed_name].extend(aliases)

    # Deduplicate and sort
    for indexed_name in updated_mappings:
        updated_mappings[indexed_name] = sorted(set(updated_mappings[indexed_name]))

    return updated_mappings, people_by_name

def to_field_set_from_record(record, fields: List[str], ):
    result = set()
    for field in fields:
        value = getattr(record, field, None)
        if isinstance(value, str):
            result.add(value)
        elif isinstance(value, list):
            result.update(value)
    return result

def matched_identity(identity_names: Dict[str, List[str]], name: str) -> str | None:
    """
    Check if a name matches any known separate identities.
    Returns the identity (canonical) name if matched, else empty string.
    """
    for canonical, identity_name_list in identity_names.items():
        names = [canonical] + identity_name_list
        for identity_name in names:
            if same_name(name, identity_name):
                return canonical
    return None

def is_weakly_tied(identity_names: Dict[str, List[str]], record1: LLMPerson | Person, record2: LLMPerson | Person) -> bool:
    """
    Determine if two records are weakly tied based on shared attributes or if they are explicitly marked as separate identities.
    """
    # If both names are in the list of separate identities 
    # (using same_name for comparison), treat them as separate
    record1_identity = matched_identity(identity_names, record1.name)
    record2_identity = matched_identity(identity_names, record2.name)
    print("record 1 identity:", record1_identity)
    print("record 2 identity:", record2_identity)

    if record1_identity and record2_identity:
        if record1_identity == record2_identity:
            return True
        else:
            return False
    
    # Check for name overlap
    if not has_name_overlap(record1.name, record2.name):
        return False

    # Check for matching roles
    if set(record1.roles) & set(record2.roles):
        return True

    # Check for overlapping email addresses
    email_overlap = to_field_set_from_record(record1, ["emails", "email"]) & to_field_set_from_record(record2, ["emails", "email"])
    if email_overlap:
        return True

    # Check for matching websites if available
    url_overlap = to_field_set_from_record(record1, ["urls", "url"]) & to_field_set_from_record(record2, ["urls", "url"])
    if url_overlap:
        return True

    return False