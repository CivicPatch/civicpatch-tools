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
    first_word = value_lower.split()[0] if value_lower.split() else value_lower
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


def normalize_designations(designations: List[str]) -> List[str]:
    if not designations:
        return []

    designation_aliases = config_utils.get_designation_alias_map()
    normalized = []

    for designation in designations:
        if designation is None or designation == "":
            continue

        designation = str(designation).strip()
        if not designation:
            continue

        clean_designation = (
            designation.split("(")[0].strip() if "(" in designation else designation.strip()
        )
        clean_designation = clean_designation.replace("#", "").replace("  ", " ").strip()

        words = clean_designation.split()
        if not words:
            continue

        parts = []
        designation_matches = []
        i = 0
        while i < len(words):
            if i + 1 < len(words):
                two_word = f"{words[i].lower()} {words[i + 1].lower()}"
                if two_word in designation_aliases:
                    designation_matches.append({
                        "start": i, "end": i + 2,
                        "type": designation_aliases[two_word],
                        "original": f"{words[i]} {words[i + 1]}",
                    })
                    i += 2
                    continue
            if words[i].lower() in designation_aliases:
                designation_matches.append({
                    "start": i, "end": i + 1,
                    "type": designation_aliases[words[i].lower()],
                    "original": words[i],
                })
                i += 1
                continue
            i += 1

        if not designation_matches:
            if len(words) >= 2:
                first_normalized = normalize_remaining_text(words[0])
                if (
                    first_normalized.isdigit()
                    and first_normalized != words[0]
                    and words[1].lower() in designation_aliases
                ):
                    designation_type = designation_aliases[words[1].lower()]
                    parts.append(f"{designation_type.title()} {first_normalized}")

            elif len(words) >= 2:
                last_word_lower = words[-1].lower()
                if last_word_lower in designation_aliases:
                    designation_type = designation_aliases[last_word_lower]
                    prefix_text = " ".join(words[:-1]).strip(" .,;:-")
                    normalized_prefix = normalize_remaining_text(prefix_text)
                    if normalized_prefix.lower() == prefix_text.lower():
                        parts.append(f"{designation_type.title()} {prefix_text.title()}")
                    else:
                        parts.append(f"{designation_type.title()} {normalized_prefix}")

            if not parts:
                result_words = []
                for word in words:
                    normalized_word = normalize_remaining_text(word)
                    if normalized_word != word and (
                        word.lower().endswith(("st", "nd", "rd", "th"))
                        or word.lower() in _ROMAN_MAP
                    ):
                        result_words.append(normalized_word)
                    else:
                        result_words.append(word)
                parts.append(" ".join(result_words))

        else:
            if (
                len(designation_matches) == 1
                and designation_matches[0]["start"] > 0
                and designation_matches[0]["end"] == len(words)
            ):
                match = designation_matches[0]
                prefix_text = " ".join(words[: match["start"]]).strip(" .,;:-")
                normalized_prefix = normalize_remaining_text(prefix_text)
                if normalized_prefix.lower() == prefix_text.lower():
                    parts.append(f"{match['type'].title()} {prefix_text.title()}")
                else:
                    parts.append(f"{match['type'].title()} {normalized_prefix}")

            else:
                for j, match in enumerate(designation_matches):
                    content_start = match["end"]
                    content_end = designation_matches[j + 1]["start"] if j + 1 < len(designation_matches) else len(words)
                    content_words = words[content_start:content_end]
                    if content_words:
                        content_text = " ".join(content_words).strip(" .,;:-")
                        normalized_content = normalize_remaining_text(content_text)
                        if normalized_content.lower() == content_text.lower():
                            parts.append(f"{match['type'].title()} {content_text.title()}")
                        else:
                            parts.append(f"{match['type'].title()} {normalized_content}")
                    else:
                        parts.append(match["type"].title())

        normalized.extend(parts)

    seen = set()
    result = []
    for item in normalized:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return sort_designations(result)


def jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid: str) -> str:
    return jurisdiction_ocdid.rsplit('/', 1)[0].replace("ocd-jurisdiction", "ocd-division")


def division_ocdid_to_designation(division_ocdid: str | None, jurisdiction_ocdid: str) -> List[str]:
    if not division_ocdid:
        return []
    division_base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)
    if division_ocdid == division_base:
        return []
    match = re.search(r"/([^/:]+):(\d+)$", division_ocdid)
    if not match:
        return []
    ocd_slug, value = match.group(1), match.group(2)
    # council_district is the OCD-ID slug for "district" per format_division
    canonical = "district" if ocd_slug == "council_district" else ocd_slug
    return [f"{canonical.title()} {value}"]


def filter_geographic_designations(designations: List[str]) -> List[str]:
    designation_configs = config_utils.get_designations()
    result = []
    for d in designations:
        if not d or not d.strip():
            continue
        key = d.strip().lower().split()[0]
        if designation_configs.get(key, {}).get("has_geographic_area", False):
            result.append(d.strip().lower())
    return result


def format_division(division_base: str, designation_key: str, designation_value: str) -> str:
    key = "council_district" if designation_key == "district" else designation_key
    return f"{division_base}/{key}:{designation_value}"


def extract_role_names_and_division_from_designations(
    designation_configs, jurisdiction_ocdid: str, office_designations: List[str]
) -> Tuple[List[str], str]:
    role_names = []
    division = None
    division_base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)

    for designation_string in office_designations:
        parts = designation_string.lower().split(' ')
        designation_key = parts[0]
        designation_value = ' '.join(parts[1:]).strip()
        if designation_key in designation_configs:
            config = designation_configs[designation_key]
            if config.get("has_geographic_area", False) and designation_value:
                division = format_division(division_base, designation_key, designation_value)
            else:
                role_names.append(designation_string)
        else:
            role_names.append(designation_string)

    if division is None:
        division = division_base

    return role_names, division
