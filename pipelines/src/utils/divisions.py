import re
from typing import List

import shared.utils.config_utils as config_utils


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
        if designation_configs.get(cleaned.split()[0], {}).get(
            "has_geographic_area", False
        ):
            result.append(cleaned)
    return result


def format_division(
    division_base: str, designation_key: str, designation_value: str
) -> str:
    key = "council_district" if designation_key == "district" else designation_key
    return f"{division_base}/{key}:{designation_value}"


def _is_division(designation: str, configs: dict) -> bool:
    key, _, value = designation.lower().partition(" ")
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
            key, _, value = d.lower().partition(" ")
            return format_division(division_base, key, value)
    return division_base
