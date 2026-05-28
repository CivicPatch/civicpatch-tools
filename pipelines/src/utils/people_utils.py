from typing import List, Dict
import shared.utils.config_utils as config_utils
from domain.models import Person, Official, Office
from runners.people_collector.schemas import ResearchedPerson
from utils.role_utils import fuzzy_match_role
from utils.designation_utils import (
    generic_sort_key,
    get_designation_priority,
    extract_designation_value,
    designations_without_division,
    resolve_division,
    division_ocdid_to_designation,
)


def filter_people_by_roles(role_configs, people: List[ResearchedPerson]):
    valid_roles = {
        name.strip().lower()
        for entry in role_configs
        for name in [entry.role] + entry.aliases
    }
    return [
        person for person in people
        if any(r.strip().lower() in valid_roles for r in person.roles)
    ]


def normalize_roles(roles: List[str], role_config=None) -> List[str]:
    """
    Normalize roles using configured aliases.
    Tries progressively shorter suffixes to handle location prefixes
    like "Seattle City Councilmember" -> "city councilmember" -> "council member".

    Strings that match a known designation are dropped — they belong in designations.
    """
    if not roles:
        return []

    role_aliases = config_utils.get_role_alias_map(role_config)
    designation_aliases = config_utils.get_designation_alias_map()
    excluded = config_utils.get_excluded_role_names(role_config)
    seen: dict[str, str] = {}

    expanded_roles = []
    for role in roles:
        if not role:
            continue
        for part in str(role).split("/"):
            part = part.strip()
            if part:
                expanded_roles.append(part)

    for role in expanded_roles:
        role_lower = role.lower().replace('-', ' ')

        # Drop anything that matches a known designation
        if designation_aliases.get(role_lower):
            continue

        # Drop explicitly excluded roles
        if role_lower in excluded:
            continue

        # Try exact match first
        direct_match = role_aliases.get(role_lower)
        if direct_match:
            seen[direct_match.lower()] = direct_match
            continue

        # Try progressively shorter suffixes
        # "Seattle City Councilmember" -> "City Councilmember" -> "Councilmember"
        words = role_lower.split()
        matched = False
        for i in range(1, len(words)):
            suffix = " ".join(words[i:])
            suffix_match = role_aliases.get(suffix)
            if suffix_match:
                seen[suffix_match.lower()] = suffix_match
                matched = True
                break

        if not matched:
            fuzzy = fuzzy_match_role(role_lower, role_aliases)
            if fuzzy and fuzzy.lower() not in excluded:
                seen[fuzzy.lower()] = fuzzy
            else:
                seen.setdefault(role.lower(), role)

    return sort_roles(list(seen.values()), role_config)


def office_name_to_roles(office_name: str, role_config=None) -> List[str]:
    if not office_name or office_name == "Unknown Office":
        return []
    parts = [p.strip() for p in office_name.split(" - ") if p.strip()]
    role_alias_map = config_utils.get_role_alias_map(role_config)
    if not role_alias_map:
        return parts
    return [p for p in parts if role_alias_map.get(p.lower())]


def get_role_priority(role_config=None) -> Dict[str, int]:
    return {
        entry.role.lower(): idx
        for idx, entry in enumerate(config_utils.get_role_configs(role_config))
    }


def sort_roles(roles: List[str], role_config=None) -> List[str]:
    role_priority = get_role_priority(role_config)
    designation_priority = get_designation_priority()
    return sorted(
        roles,
        key=lambda r: generic_sort_key(r, role_priority, designation_priority)
    )


def sort_people(people: List[Person], role_config=None) -> List[Person]:
    role_priority = get_role_priority(role_config)
    designation_priority = get_designation_priority()

    def person_sort_key(person: Person):
        role_priorities = [
            role_priority.get(role.lower().strip(), 9999)
            for role in person.roles
        ] if person.roles else [9999]
        min_role_priority = min(role_priorities)

        designation_priorities = [
            designation_priority.get(designation.lower().split()[0], 9999)
            for designation in person.designations if designation
        ] if person.designations else [9999]
        min_designation_priority = min(designation_priorities)

        designation_numbers = [
            extract_designation_value(designation)
            for designation in person.designations if designation
        ] if person.designations else [None]
        min_designation_number = min([n for n in designation_numbers if n is not None], default=9999)

        return (min_role_priority, min_designation_priority, min_designation_number)

    return sorted(people, key=person_sort_key)


def person_to_official(person: Person) -> Official:
    office_names = list(dict.fromkeys(person.roles + designations_without_division(person.designations)))
    office_name = " - ".join(office_names) if office_names else "Unknown Office"
    return Official(
        id="", # to be filled in later after resolving with API
        name=person.name,
        other_names=person.other_names,
        phones=person.phones,
        emails=person.emails,
        urls=person.urls,
        start_date=person.start_date or None,
        end_date=person.end_date or None,
        office=Office(
            name=office_name.title(),
            division_ocdid=resolve_division(person.jurisdiction_ocdid, person.designations),
        ),
        image=person.image,
        jurisdiction_ocdid=person.jurisdiction_ocdid,
        cdn_image=person.cdn_image,
        source_urls=person.source_urls,
        updated_at=person.updated_at or "",
    )


def official_to_person(official: Official) -> Person:
    return Person(
        name=official.name,
        other_names=official.other_names,
        roles=office_name_to_roles(official.office.name),
        designations=division_ocdid_to_designation(official.office.division_ocdid, official.jurisdiction_ocdid),
        phones=official.phones,
        emails=official.emails,
        urls=official.urls,
        start_date=official.start_date,
        end_date=official.end_date,
        image=official.image,
        jurisdiction_ocdid=official.jurisdiction_ocdid,
        cdn_image=official.cdn_image,
        source_urls=official.source_urls,
        updated_at=official.updated_at,
    )
