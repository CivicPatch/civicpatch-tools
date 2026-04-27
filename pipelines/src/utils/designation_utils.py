from typing import List, Dict, Tuple
import re
import shared.utils.config_utils as config_utils

WORD_TO_NUMBER = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5',
    'sixth': '6', 'seventh': '7', 'eighth': '8', 'ninth': '9', 'tenth': '10',
    'eleventh': '11', 'twelfth': '12', 'thirteenth': '13', 'fourteenth': '14',
    'fifteenth': '15', 'sixteenth': '16', 'seventeenth': '17', 'eighteenth': '18',
    'nineteenth': '19', 'twentieth': '20',
}

_ROMAN_MAP = {
    "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
    "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
}


def normalize_remaining_text(text: str) -> str:
    if not text:
        return ""
    text_lower = text.lower().strip()
    if text_lower in WORD_TO_NUMBER:
        return WORD_TO_NUMBER[text_lower]
    if text_lower in _ROMAN_MAP:
        return _ROMAN_MAP[text_lower]
    for suffix in ["st", "nd", "rd", "th"]:
        if text_lower.endswith(suffix):
            number = text_lower[: -len(suffix)]
            if number.isdigit():
                return number
    if text_lower.isdigit():
        return text_lower
    return text


def extract_designation_value(designation: str):
    if not designation:
        return None
    match = re.search(r"\b(\d+)\b", designation)
    return int(match.group(1)) if match else None


def get_designation_priority() -> Dict[str, int]:
    designation_configs = config_utils.get_designations()
    return {name.lower(): idx for idx, name in enumerate(designation_configs.keys())}


def generic_sort_key(
    value: str,
    primary_priority: dict,
    secondary_priority: dict | None = None,
):
    value_lower = value.lower().strip()
    primary = primary_priority.get(value_lower)
    if primary is not None:
        secondary = (1, secondary_priority.get(value_lower, 9999) if secondary_priority else 9999)
        return (primary, secondary)
    words = value_lower.split()
    first_word = words[0] if words else value_lower
    primary = primary_priority.get(first_word, 9999)
    number = extract_designation_value(value)
    if number is not None:
        secondary = (0, number)
    elif secondary_priority:
        secondary = (1, secondary_priority.get(first_word, 9999))
    else:
        secondary = (1, 9999)
    return (primary, secondary)


def sort_designations(designations: List[str]) -> List[str]:
    designation_priority = get_designation_priority()
    return sorted(designations, key=lambda d: generic_sort_key(d, designation_priority))


def _clean_to_words(designation: str) -> List[str]:
    if not designation:
        return []
    s = str(designation).strip()
    s = s.split("(")[0].strip()
    s = s.replace("#", "").replace("  ", " ").strip()
    return s.split()


def _find_keyword_matches(words: List[str], aliases: dict) -> List[dict]:
    matches = []
    i = 0
    while i < len(words):
        if i + 1 < len(words):
            two_word = f"{words[i].lower()} {words[i + 1].lower()}"
            if two_word in aliases:
                matches.append({"start": i, "end": i + 2, "type": aliases[two_word]})
                i += 2
                continue
        if words[i].lower() in aliases:
            matches.append({"start": i, "end": i + 1, "type": aliases[words[i].lower()]})
            i += 1
            continue
        i += 1
    return matches


def _format_type_content(designation_type: str, text: str) -> str:
    text = text.strip(" .,;:-")
    normalized = normalize_remaining_text(text)
    suffix = text.title() if normalized.lower() == text.lower() else normalized
    return f"{designation_type.title()} {suffix}"


def _normalize_word(word: str) -> str:
    """Normalize a single word if it's an ordinal or roman numeral, otherwise return as-is."""
    w = word.lower()
    if w.endswith(("st", "nd", "rd", "th")) or w in _ROMAN_MAP:
        normalized = normalize_remaining_text(word)
        if normalized != word:
            return normalized
    return word


def _apply_matches(words: List[str], matches: List[dict], aliases: dict) -> List[str]:
    if not matches:
        # ordinal before keyword: "1st Ward" → "Ward 1"
        if len(words) >= 2:
            first_normalized = normalize_remaining_text(words[0])
            if first_normalized.isdigit() and first_normalized != words[0] and words[1].lower() in aliases:
                return [f"{aliases[words[1].lower()].title()} {first_normalized}"]
        # fallback: normalize ordinals/romans in place, keep everything else as-is
        return [" ".join(_normalize_word(w) for w in words)]

    # single keyword at end with prefix: "North Ward" → "Ward North", "Council District 3" → "District 3"
    if len(matches) == 1 and matches[0]["start"] > 0 and matches[0]["end"] == len(words):
        prefix = " ".join(words[:matches[0]["start"]])
        return [_format_type_content(matches[0]["type"], prefix)]

    # keyword(s) with content after: "District 1", "At-Large Position 8" → ["At-Large", "Position 8"]
    parts = []
    for j, match in enumerate(matches):
        content_end = matches[j + 1]["start"] if j + 1 < len(matches) else len(words)
        content_words = words[match["end"]:content_end]
        if content_words:
            parts.append(_format_type_content(match["type"], " ".join(content_words)))
        else:
            parts.append(match["type"].title())
    return parts


def normalize_designations(designations: List[str]) -> List[str]:
    if not designations:
        return []
    aliases = config_utils.get_designation_alias_map()
    normalized = []
    for designation in designations:
        words = _clean_to_words(designation)
        if words:
            matches = _find_keyword_matches(words, aliases)
            normalized.extend(_apply_matches(words, matches, aliases))
    return sort_designations(list(dict.fromkeys(normalized)))


def jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid: str) -> str:
    return jurisdiction_ocdid.rsplit('/', 1)[0].replace("ocd-jurisdiction", "ocd-division")


def division_ocdid_to_designation(division_ocdid: str | None, jurisdiction_ocdid: str) -> List[str]:
    if not division_ocdid:
        return []
    division_base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)
    if division_ocdid == division_base:
        return []
    match = re.search(r"/([^/:]+):([^/]+)$", division_ocdid)
    if not match:
        return []
    ocd_slug, value = match.group(1), match.group(2)
    # council_district is the OCD-ID slug for "district" per format_division
    canonical = "district" if ocd_slug == "council_district" else ocd_slug
    return [f"{canonical.title()} {value.upper() if len(value) == 1 else value}"]


def filter_geographic_designations(designations: List[str]) -> List[str]:
    designation_configs = config_utils.get_designations()
    result = []
    for d in designations:
        cleaned = d.strip().lower() if d else ""
        if not cleaned:
            continue
        if designation_configs.get(cleaned.split()[0], {}).get("has_geographic_area", False):
            result.append(cleaned)
    return result


def format_division(division_base: str, designation_key: str, designation_value: str) -> str:
    key = "council_district" if designation_key == "district" else designation_key
    return f"{division_base}/{key}:{designation_value}"


def _is_division(designation: str, configs: dict) -> bool:
    key, _, value = designation.lower().partition(' ')
    return configs.get(key, {}).get("has_geographic_area", False) and bool(value)


def designations_without_division(designations: List[str]) -> List[str]:
    configs = config_utils.get_designations()
    return [d for d in designations if not _is_division(d, configs)]


def resolve_division(jurisdiction_ocdid: str, designations: List[str]) -> str:
    # Only ward and district are division types; officials have at most one.
    configs = config_utils.get_designations()
    division_base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)
    for d in designations:
        if _is_division(d, configs):
            key, _, value = d.lower().partition(' ')
            return format_division(division_base, key, value)
    return division_base
