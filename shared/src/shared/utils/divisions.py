import re
from typing import List

import shared.utils.config_utils as config_utils

# The trailing `/slug:value` of a division ocdid. This is the one place it is matched; every
# reader of a division's type and number goes through `_division_tail`.
_DIVISION_TAIL = re.compile(r"/([^/:]+):([^/]+)$")


def _division_tail(division_ocdid: str | None) -> tuple[str, str] | None:
    match = _DIVISION_TAIL.search(division_ocdid or "")
    if match is None:
        return None
    return (match.group(1), match.group(2))


def numbered_division_label(division_ocdid: str | None) -> tuple[str, int] | None:
    """("council district", 3) for a division whose value is a number, else None.

    The ocdid's own slug, spaced, not the canonical designation: the numbering-gap message names
    the division the way the ocdid does.
    """
    tail = _division_tail(division_ocdid)
    if tail is None or not tail[1].isdigit():
        return None
    return (tail[0].replace("_", " "), int(tail[1]))


def jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid: str) -> str:
    return jurisdiction_ocdid.rsplit("/", 1)[0].replace(
        "ocd-jurisdiction", "ocd-division"
    )


def division_ocdid_to_designation(
    division_ocdid: str | None, jurisdiction_ocdid: str
) -> List[str]:
    if not division_ocdid:
        return []
    division_base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)
    if division_ocdid == division_base:
        return []
    tail = _division_tail(division_ocdid)
    if tail is None:
        return []
    ocd_slug, value = tail
    # council_district is the OCD-ID slug for "district" per format_division
    canonical = "district" if ocd_slug == "council_district" else ocd_slug
    return [f"{canonical.title()} {value.upper() if len(value) == 1 else value}"]


def filter_divisions(designations: List[str]) -> List[str]:
    configs = config_utils.get_designations()
    return [
        d.strip().lower()
        for d in designations
        if d and is_division(d.strip(), configs)
    ]


def format_division(
    division_base: str, designation_key: str, designation_value: str
) -> str:
    key = "council_district" if designation_key == "district" else designation_key
    return f"{division_base}/{key}:{designation_value}"


def is_division(designation: str, configs: dict) -> bool:
    # A division keyword always carries a value ("ward 3", "district 5"); at-large is the
    # only valueless keyword and is not a division, so it needs no special case.
    key, _, value = designation.lower().partition(" ")
    return configs.get(key, {}).get("is_division", False) and bool(value)


def designations_without_division(designations: List[str]) -> List[str]:
    configs = config_utils.get_designations()
    return [d for d in designations if not is_division(d, configs)]


def resolve_division(jurisdiction_ocdid: str, designations: List[str]) -> str:
    # Only ward and district are division types; officials have at most one.
    configs = config_utils.get_designations()
    division_base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)
    for d in designations:
        if is_division(d, configs):
            key, _, value = d.lower().partition(" ")
            return format_division(division_base, key, value)
    return division_base
