from typing import NamedTuple

from rapidfuzz import fuzz, process
from shared.utils import config_utils
from shared.utils.config_utils import RoleConfig

FUZZY_SCORE_CUTOFF = 85
UNRANKED = float("inf")


def lookup_key(label: str) -> str:
    return label.lower().replace("-", " ").strip()


def _keyed_aliases(alias_map: dict[str, str]) -> dict[str, str]:
    return {lookup_key(alias): canonical for alias, canonical in alias_map.items()}


class Taxonomy(NamedTuple):
    role_aliases: dict[str, str]  # key -> canonical role name
    designation_aliases: dict[str, str]  # key -> canonical designation name
    role_priority: dict[str, int]  # canonical role -> sort index
    designation_priority: dict[str, int]


def build_taxonomy(role_config: RoleConfig | None) -> Taxonomy:
    role_entries = config_utils.get_role_configs(role_config)
    designations = config_utils.get_designations()
    role_aliases = _keyed_aliases(config_utils.get_role_alias_map(role_config))
    designation_aliases = _keyed_aliases(config_utils.get_designation_alias_map())

    return Taxonomy(
        role_aliases=role_aliases,
        designation_aliases=designation_aliases,
        role_priority={
            lookup_key(entry.role): i for i, entry in enumerate(role_entries)
        },
        designation_priority={
            lookup_key(name): i for i, name in enumerate(designations)
        },
    )


def resolve_role(label: str, taxonomy: Taxonomy) -> str | None:
    """The canonical role this label names, or None if it names no known role."""
    if is_designation(label, taxonomy):
        return None

    label_key = lookup_key(label)
    if label_key in taxonomy.role_aliases:
        return taxonomy.role_aliases[label_key]

    # Shed location prefixes: "Seattle City Councilmember" -> "City Councilmember" -> "Councilmember"
    words = label_key.split()
    for i in range(1, len(words)):
        suffix = " ".join(words[i:])
        if suffix in taxonomy.role_aliases:
            return taxonomy.role_aliases[suffix]

    return _fuzzy_match(label_key, taxonomy.role_aliases)


def _fuzzy_match(label_key: str, aliases: dict[str, str]) -> str | None:
    match = process.extractOne(
        label_key, aliases.keys(), scorer=fuzz.ratio, score_cutoff=FUZZY_SCORE_CUTOFF
    )
    return aliases[match[0]] if match else None


def role_sort_key(role: str, taxonomy: Taxonomy) -> tuple:
    role_key = lookup_key(role)
    return (taxonomy.role_priority.get(role_key, UNRANKED), role_key)


def _value_sort_key(rest: str) -> tuple[int, int, str]:
    if rest.isdigit():
        return (0, int(rest), "")
    if rest:
        return (1, 0, rest)
    return (2, 0, "")


def is_designation(label: str, taxonomy: Taxonomy) -> bool:
    return split_designation(label, taxonomy) is not None


def _is_designation_value(tail: str):
    return tail == "" or tail.isdigit() or len(tail) == 1


def split_designation(label: str, taxonomy: Taxonomy) -> tuple[str, str] | None:
    """("ward", "3") for "Ward 3" or "Council Ward 3"."""
    words = lookup_key(label).split()
    for i in range(len(words), 0, -1):
        canonical = taxonomy.designation_aliases.get(" ".join(words[:i]))
        if canonical:
            value = " ".join(words[i:])

            if not _is_designation_value(value):
                return None
            return (canonical, value)
    return None


def designation_sort_key(designation: str, taxonomy: Taxonomy) -> tuple:
    split = split_designation(designation, taxonomy)
    if split is None:
        return (UNRANKED, _value_sort_key(""))
    canonical, value = split
    return (
        taxonomy.designation_priority.get(lookup_key(canonical), UNRANKED),
        _value_sort_key(value),
    )


def sort_roles(roles: list[str], taxonomy: Taxonomy) -> list[str]:
    return sorted(roles, key=lambda role: role_sort_key(role, taxonomy))


def sort_designations(designations: list[str], taxonomy: Taxonomy) -> list[str]:
    return sorted(designations, key=lambda d: designation_sort_key(d, taxonomy))


WORD_TO_NUMBER = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
    "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10",
    "eleventh": "11", "twelfth": "12", "thirteenth": "13", "fourteenth": "14",
    "fifteenth": "15", "sixteenth": "16", "seventeenth": "17", "eighteenth": "18",
    "nineteenth": "19", "twentieth": "20",
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


def _clean_to_words(designation: str) -> list[str]:
    if not designation:
        return []
    s = str(designation).strip()
    s = s.split("(")[0].strip()
    s = s.replace("#", "").replace("  ", " ").strip()
    return s.split()


def _find_keyword_matches(words: list[str], aliases: dict[str, str]) -> list[dict]:
    matches = []
    i = 0
    while i < len(words):
        if i + 1 < len(words):
            two_word = lookup_key(f"{words[i]} {words[i + 1]}")
            if two_word in aliases:
                matches.append({"start": i, "end": i + 2, "type": aliases[two_word]})
                i += 2
                continue
        if lookup_key(words[i]) in aliases:
            matches.append(
                {"start": i, "end": i + 1, "type": aliases[lookup_key(words[i])]}
            )
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
    """Ordinals and roman numerals become digits; everything else passes through."""
    w = word.lower()
    if w.endswith(("st", "nd", "rd", "th")) or w in _ROMAN_MAP:
        normalized = normalize_remaining_text(word)
        if normalized != word:
            return normalized
    return word


def _apply_matches(
    words: list[str], matches: list[dict], aliases: dict[str, str]
) -> list[str]:
    if not matches:
        # ordinal before keyword: "1st Ward" → "Ward 1"
        if len(words) >= 2:
            first_normalized = normalize_remaining_text(words[0])
            if (
                first_normalized.isdigit()
                and first_normalized != words[0]
                and lookup_key(words[1]) in aliases
            ):
                return [f"{aliases[lookup_key(words[1])].title()} {first_normalized}"]
        # fallback: normalize ordinals/romans in place, keep everything else as-is
        return [" ".join(_normalize_word(w) for w in words)]

    # single keyword at end with prefix: "North Ward" → "Ward North", "Council District 3" → "District 3"
    if len(matches) == 1 and matches[0]["start"] > 0 and matches[0]["end"] == len(words):
        prefix = " ".join(words[: matches[0]["start"]])
        return [_format_type_content(matches[0]["type"], prefix)]

    # keyword(s) with content after: "District 1", "At-Large Position 8" → ["At-Large", "Position 8"]
    parts = []
    for j, match in enumerate(matches):
        content_end = matches[j + 1]["start"] if j + 1 < len(matches) else len(words)
        content_words = words[match["end"] : content_end]
        if content_words:
            parts.append(_format_type_content(match["type"], " ".join(content_words)))
        else:
            parts.append(match["type"].title())
    return parts


def normalize_designations(designations: list[str], taxonomy: Taxonomy) -> list[str]:
    if not designations:
        return []
    normalized = []
    for designation in designations:
        words = _clean_to_words(designation)
        if words:
            matches = _find_keyword_matches(words, taxonomy.designation_aliases)
            normalized.extend(
                _apply_matches(words, matches, taxonomy.designation_aliases)
            )
    return sort_designations(list(dict.fromkeys(normalized)), taxonomy)


def normalize_roles(labels: list[str], taxonomy: Taxonomy) -> list[str]:
    """Resolve each label to its canonical role, keeping unresolved labels verbatim.
    Designations are dropped — they belong in designations."""
    resolved: dict[str, str] = {}
    for label in labels:
        if not label:
            continue
        for part in _split_on_slash(str(label)):
            if is_designation(part, taxonomy):
                continue
            name = resolve_role(part, taxonomy) or part
            resolved.setdefault(lookup_key(name), name)
    return sort_roles(list(resolved.values()), taxonomy)


def _split_on_slash(label: str) -> list[str]:
    """ "Mayor/City Clerk" is two labels."""
    return [part.strip() for part in label.split("/") if part.strip()]
