#from schemas import People
from typing import List, Dict
import re
import utils.config_utils as config_utils
from schemas import Person, ResearchedPerson

def filter_people_by_roles(role_configs, people: List[ResearchedPerson]):
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
        person_roles = [r.strip().lower() for r in person.roles]
        if any(role in valid_roles for role in person_roles):
            filtered.append(person)

    return filtered

def normalize_remaining_text(text: str) -> str:
    """
    Normalize text after division name:
    - Convert roman numerals to numbers
    - Convert ordinals to numbers
    - Preserve directional or other text
    
    Examples:
        >>> normalize_remaining_text("Five")
        "5"
        >>> normalize_remaining_text("V")
        "5"
        >>> normalize_remaining_text("5th")
        "5"
        >>> normalize_remaining_text("South")
        "South"
    """
    if not text:
        return ""
        
    # Map roman numerals to numbers
    roman_map = {
        'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5',
        'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'
    }
    
    # Map word numbers to digits
    word_map = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'
    }
    
    # Convert to lower for matching
    text_lower = text.lower().strip()
    
    # Check for roman numerals
    if text_lower in roman_map:
        return roman_map[text_lower]
        
    # Check for word numbers
    if text_lower in word_map:
        return word_map[text_lower]
        
    # Check for ordinals by stripping suffixes
    for suffix in ['st', 'nd', 'rd', 'th']:
        if text_lower.endswith(suffix):
            number = text_lower[:-len(suffix)]
            if number.isdigit():
                return number
                
    # If it's already a number, return it
    if text_lower.isdigit():
        return text_lower
        
    # Otherwise return original text
    return text

def normalize_roles(logger, government_type: str, roles: List[str]) -> List[str]:
    """
    Normalize roles using configured aliases.
    """
    if not roles:
        return []

    role_aliases = config_utils.get_role_alias_map(government_type)
    seen = set()

    for role in roles:
        role = str(role).strip().lower()

        direct_match = role_aliases.get(role)
        if direct_match:
            seen.add(direct_match)
        else:
            logger.warning(f"Role '{role}' not found in aliases for government type '{government_type}'. Keeping original.")

    return [r.title() for r in seen]

def normalize_divisions(divisions: List[str]) -> List[str]:
    """
    Normalize divisions using configured aliases.
    """
    if not divisions:
        return []

    division_aliases = config_utils.get_division_alias_map()
    normalized = []

    for division in divisions:
        division = str(division).strip()
        if not division:
            continue
            
        # Clean parenthetical content
        clean_division = division.split('(')[0].strip() if '(' in division else division.strip()
        words = clean_division.split()
        
        if not words:
            continue
        
        parts = []
        
        # Find all division types and their positions
        division_matches = []
        i = 0
        while i < len(words):
            # Check two-word combinations first
            if i + 1 < len(words):
                two_word = f"{words[i].lower()} {words[i + 1].lower()}"
                if two_word in division_aliases:
                    division_matches.append({
                        'start': i,
                        'end': i + 2,
                        'type': division_aliases[two_word],
                        'original': f"{words[i]} {words[i + 1]}"
                    })
                    i += 2
                    continue
            
            # Check single words
            if words[i].lower() in division_aliases:
                division_matches.append({
                    'start': i,
                    'end': i + 1,
                    'type': division_aliases[words[i].lower()],
                    'original': words[i]
                })
                i += 1
                continue
                
            i += 1
        
        if not division_matches:
            # No division types found - handle special cases and fallback
            
            # Check for ordinal + division pattern (e.g. "1st Ward" -> "Ward 1")
            if len(words) >= 2:
                first_normalized = normalize_remaining_text(words[0])
                if (first_normalized.isdigit() and 
                    first_normalized != words[0] and 
                    words[1].lower() in division_aliases):
                    division_type = division_aliases[words[1].lower()]
                    parts.append(f"{division_type.title()} {first_normalized}")
            
            # Check for directional + division pattern (e.g. "North Ward" -> "Ward North")
            elif len(words) >= 2:
                last_word_lower = words[-1].lower()
                if last_word_lower in division_aliases:
                    division_type = division_aliases[last_word_lower]
                    prefix_words = words[:-1]
                    prefix_text = " ".join(prefix_words)
                    # Clean up punctuation
                    prefix_text = prefix_text.strip(' .,;:-')
                    normalized_prefix = normalize_remaining_text(prefix_text)
                    
                    # If prefix didn't change (like "North"), it's directional
                    if normalized_prefix.lower() == prefix_text.lower():
                        parts.append(f"{division_type.title()} {prefix_text.title()}")
                    else:
                        parts.append(f"{division_type.title()} {normalized_prefix}")
            
            # Fallback: normalize any ordinals/romans in place
            if not parts:
                result_words = []
                for word in words:
                    normalized_word = normalize_remaining_text(word)
                    if (normalized_word != word and 
                        (word.lower().endswith(('st', 'nd', 'rd', 'th')) or
                         word.lower() in ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'])):
                        result_words.append(normalized_word)
                    else:
                        result_words.append(word)
                parts.append(" ".join(result_words))
        
        else:
            # Special case: if there's only one division and it's at the end with prefix content,
            # treat prefix as directional (e.g., "North Ward" -> "Ward North")
            if (len(division_matches) == 1 and 
                division_matches[0]['start'] > 0 and
                division_matches[0]['end'] == len(words)):
                
                match = division_matches[0]
                division_type = match['type']
                prefix_words = words[:match['start']]
                
                if prefix_words:
                    prefix_text = " ".join(prefix_words)
                    # Clean up punctuation
                    prefix_text = prefix_text.strip(' .,;:-')
                    normalized_prefix = normalize_remaining_text(prefix_text)
                    
                    # If prefix didn't change, it's likely directional
                    if normalized_prefix.lower() == prefix_text.lower():
                        parts.append(f"{division_type.title()} {prefix_text.title()}")
                    else:
                        parts.append(f"{division_type.title()} {normalized_prefix}")
                else:
                    parts.append(division_type.title())
            
            else:
                # Process divisions found in the text
                for j, match in enumerate(division_matches):
                    division_type = match['type']
                    end_idx = match['end']
                    
                    # For content, only look AFTER this division, not before
                    # (prefix content belongs to the previous division)
                    content_start = end_idx
                    content_end = len(words)
                    
                    # If there's a next division, content ends there
                    if j + 1 < len(division_matches):
                        content_end = division_matches[j + 1]['start']
                    
                    content_words = words[content_start:content_end]
                    
                    if content_words:
                        content_text = " ".join(content_words)
                        # Clean up punctuation
                        content_text = content_text.strip(' .,;:-')
                        normalized_content = normalize_remaining_text(content_text)
                        
                        # If content didn't change, preserve original case (directional words)
                        if normalized_content.lower() == content_text.lower():
                            parts.append(f"{division_type.title()} {content_text.title()}")
                        else:
                            parts.append(f"{division_type.title()} {normalized_content}")
                    else:
                        parts.append(division_type.title())
        
        normalized.extend(parts)

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for item in normalized:
        if item not in seen:
            seen.add(item)
            result.append(item)
    
    return result

def get_role_priority(government_type: str) -> Dict[str, int]:
    """
    Returns a mapping from role name (lowercase) to its priority/order in the config.
    Aliases are ignored; only main role names are used.
    """
    role_configs = config_utils.get_role_configs_by_government_type(government_type)
    priority = {}
    for idx, role_entry in enumerate(role_configs):
        role_name = role_entry["role"].lower()
        priority[role_name] = idx
    return priority

def sort_people(people: List[Person], government_type: str) -> List[Person]:
    """
    Sort people by role priority (from config), then division, then name.
    """
    role_priority = get_role_priority(government_type)

    def sort_key(person: Person):
        # Find the highest priority among person's roles
        priorities = [role_priority.get(role.lower(), 9999) for role in person.roles]
        min_priority = min(priorities) if priorities else 9999
        first_division = person.divisions[0] if person.divisions else ""
        return (min_priority, first_division, person.name)

    return sorted(people, key=sort_key)