from typing import Dict, List
from schemas import (
  PipelineContext, 
  PipelineStatus, PeopleByNameDict, 
  LLMPerson, Person,
  ProcessedLLMPeople, dict_to_pydantic, pydantic_to_dict
)
from collections import Counter
import utils.config_utils as config_utils
import re

def merge_records_within_source(context: PipelineContext):
    """
    Merge records within the same source to create a unified profile for each unique identity.
    """
    print(f"Step 6: {PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE.value}")
    data_by_llm_name: Dict[str, PeopleByNameDict] = context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value]
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]
    role_alias_map = config_utils.build_role_alias_map(government_type)

    division_alias_map = config_utils.get_division_alias_map()

    print("Merging records within source...")

    merged_records = {
        "openai": [],
        "google_gemini": []
    }

    for llm_name, people_by_name in data_by_llm_name.items():
        for person_name, llm_person_records in people_by_name.items():
            records = records_to_llm_person(
                name=person_name,
                role_alias_map=role_alias_map,
                division_alias_map=division_alias_map,
                llm_person=llm_person_records
            )
            merged_records[llm_name].append(records)

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE.value: merged_records
        }
    }

def merge_field(records, field_name):
    """
    Merge a single-value field (phone, email, website, start_date, end_date) from a list of LLMPerson records.
    Prefer non-empty, most frequent, then highest confidence.
    """
    values = [
        (getattr(r, field_name).data, getattr(r, field_name).llm_confidence, getattr(r, field_name))
        for r in records if getattr(r, field_name) and getattr(r, field_name).data
    ]
    if not values:
        return None
    value_counts = Counter([v[0] for v in values])
    most_common = value_counts.most_common(1)[0][0]
    candidates = [v for v in values if v[0] == most_common]
    best = max(candidates, key=lambda x: x[1])
    return best[2]

def merge_roles(records: List[LLMPerson], role_alias_map: Dict[str, str]) -> List[str]:
    """Collect all unique standardized roles from all records, preserving order."""
    seen = set()
    unique_roles = []
    for record in records:
        for role in record.roles:
            if not role.data:
                continue
            # Use the alias map to standardize the role
            standardized = role_alias_map.get(role.data.lower(), role.data)
            if standardized not in seen:
                seen.add(standardized)
                unique_roles.append(standardized)
    return unique_roles

def normalize_division(division: str, alias_map: Dict[str, str]) -> str:
    """
    Normalize a division string to canonical form, e.g. 'ward 5', 'citywide', 'district east'.
    Returns canonical division type + suffix (if any).
    """
    division = division.lower().strip()
    for alias, canonical in alias_map.items():
        if division.startswith(alias):
            suffix = division[len(alias):].strip()
            # Only keep suffix if it's a word or number
            if suffix:
                suffix = re.sub(r"[^a-z0-9\- ]", "", suffix)
                return f"{canonical} {suffix}".strip()
            return canonical
    return division  # fallback: return as-is if no match

def merge_divisions(division_alias_map, records: List[LLMPerson]) -> List[str]:
    """
    Normalize and merge divisions from all records: deduplicate and keep all unique divisions in order.
    Returns a list of strings.
    """
    seen = set()
    unique_divisions = []
    for record in records:
        for div in record.divisions:
            if not div.data:
                continue

            norm = normalize_division(div.data, division_alias_map)
            if norm not in seen:
                seen.add(norm)
                unique_divisions.append(norm)
    return unique_divisions


def records_to_llm_person(
    name: str,
    role_alias_map: Dict[str, str],
    division_alias_map: Dict[str, str],
    llm_person: ProcessedLLMPeople
) -> Person:
    records = [LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r for r in llm_person["records"]]
    merged_roles = merge_roles(records, role_alias_map)
    merged_divisions = merge_divisions(division_alias_map, records)
    # Helper to extract .data or return ""
    def get_field(records, field):
        val = merge_field(records, field)
        return val.data if val and val.data else ""
    person = Person(
        name=name,
        roles=merged_roles,
        divisions=merged_divisions,
        image="",
        cdn_image="",
        email=get_field(records, "email"),
        phone_number=get_field(records, "phone_number"),
        website=get_field(records, "website"),
        start_date=get_field(records, "start_date"),
        end_date=get_field(records, "end_date"),
        sources=[],
        updated_at="",
    )
    return person.model_dump()