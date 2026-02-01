from typing import List, Dict, Tuple
from domain.models import Person
from jobs.people_collector.schemas import LLMPerson, PeopleByName, OtherNamesByCanonicalName, PeopleCollectorContext
from nameparser import HumanName
from Levenshtein import distance as levenshtein_distance
import copy
import unicodedata

NAME_SIMILARITY_THRESHOLD = 4

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

def is_initial(first_name: str, candidate: str) -> bool:
    """
    Check if candidate is an initial of the name.
    "J." -> "John"
    "J" -> "John"
    """
    if len(candidate) == 1:
        return first_name.lower().startswith(candidate.lower())
    if len(candidate) == 2 and candidate[1] == '.':
        return first_name.lower().startswith(candidate[0].lower())
    return False

def has_name_overlap(name1: str, name2: str) -> bool:
    """
    Check if two names have an overlap in their first and last names.
    - First names must be similar or have overlap (e.g., partial match).
    - Last names must either match exactly or one must be a substring of the other.
    """
    # Normalize names
    first1, last1 = first_name(name1), last_name(name1)
    first2, last2 = first_name(name2), last_name(name2)
    
    if not first1 or not first2:
        return False
    if not last1 or not last2:
        return False

    # Check if last names match or one is a substring of the other
    if last1.lower() == last2.lower() or last1.lower() in last2.lower() or last2.lower() in last1.lower():
        # Case 1: First name matches exactly
        if first1.lower() == first2.lower():
            return True

        # Case 2: One of the first names is an initial of the other
        if is_initial(first1, first2) or is_initial(first2, first1):
            return True
    
        # Case 3: First name is a subset of the other or similar
        if first1.lower() in first2.lower() or first2.lower() in first1.lower():
            return True
        
        # Case 4: First names are similar based on Levenshtein distance
        if are_names_similar(first1, first2):
            return True

    return False

def are_names_similar(name1: str, name2: str, threshold: int = NAME_SIMILARITY_THRESHOLD) -> bool:
    """
    Compare two names (usually first name only) using Levenshtein distance and determine if they are similar.
    """
    return levenshtein_distance(name1, name2) <= threshold

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
        if first_name(normalized_name) == first_name(existing_name) and \
            (last_name(normalized_name) in last_name(existing_name) or \
            last_name(existing_name) in last_name(normalized_name)):
                return existing_name
        if last_name(normalized_name) == last_name(existing_name):
            # Check if first name meets the threshold
            if are_names_similar(first_name(normalized_name), first_name(existing_name)):
                return existing_name

    return normalized_name

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

def group_people_by_name(known_mappings: Dict[str, List[str]], people_by_name: Dict[str, List[LLMPerson]], people_to_link: List[LLMPerson]) -> Dict[str, List[LLMPerson]]:
    """
    Group people by name, preserving known mappings and adding new people to the appropriate groups.
    """
    updated_people = copy.deepcopy(people_by_name)

    # Process people_to_link
    for person in people_to_link:
        normalized_name = normalize_name(person.name)
        matched = False
        for canonical_name, aliases in known_mappings.items():
            if normalized_name == normalize_name(canonical_name) or normalized_name in [normalize_name(alias) for alias in aliases]:
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

    if record1_identity and record2_identity:
        if record1_identity == record2_identity:
            return True
        else:
            return False
    
    # Check for name overlap
    if not has_name_overlap(record1.name, record2.name):
        return False

    # Check for matching designations
    if set(record1.designations) & set(record2.designations):
        return True
    
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