from typing import Dict, List
from schemas import PipelineContext, PipelineStatus, PeopleByNameDict, LLMPerson, ProcessedLLMPeople, dict_to_pydantic
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
    role_configs = config_utils.get_role_configs_by_government_type(government_type)
    division_alias_map = config_utils.get_division_alias_map()

    print("Merging records within source...")
    print(processed_llm_people)

    merged_records = [{
        "source_name": llm_name,
        "data": []
    }]

    for llm_name, processed_llm_people in data_by_llm_name.items():
        if not processed_llm_people["records"]:
            continue

        records_to_llm_person = records_to_llm_person(
            name=processed_llm_people["name"],
            role_configs=role_configs,
            division_alias_map=division_alias_map,
            processed_llm_people=processed_llm_people
        )

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE.value: {
                "data": merged_records
            }
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

def merge_roles(records: List[LLMPerson], role_configs: dict) -> List[str]:
    """Merge roles from all records: standardize, count, pick most frequent."""
    all_roles = []
    for record in records:
        all_roles.extend([role_configs.get(role.data, role.data) for role in record.roles])
    if not all_roles:
        return []
    role_counts = Counter(all_roles)
    most_common_role, _ = role_counts.most_common(1)[0]
    return [role for role in all_roles if role == most_common_role]

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
    """Normalize and merge divisions from all records: count, pick most frequent."""
    all_divisions = []
    for record in records:
        for div in record.divisions:
            if div.data:
                norm = normalize_division(div.data, division_alias_map)

                if norm not in all_divisions:
                    all_divisions.append(norm)
    if not all_divisions:
        return []

    division_counts = Counter(all_divisions)
    most_common_division, _ = division_counts.most_common(1)[0]
    return [div for div in all_divisions if div == most_common_division]


def records_to_llm_person(
    name: str,
    role_configs: dict,
    division_alias_map: Dict[str, str],
    processed_llm_people: ProcessedLLMPeople
) -> LLMPerson:
    """
    Merge a list of LLMPerson records into a single LLMPerson object, field by field.
    """
    # Ensure all records are LLMPerson instances
    records = [
        LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r
        for r in processed_llm_people["records"]
    ]

    merged_roles = merge_roles(records, role_configs)
    merged_divisions = merge_divisions(division_alias_map, records)

    return LLMPerson(
        name=name,
        roles=[role_configs.get(role, role) for role in merged_roles],
        divisions=merged_divisions,
        phone_number=merge_field(records, "phone_number"),
        email=merge_field(records, "email"),
        website=merge_field(records, "website"),
        start_date=merge_field(records, "start_date"),
        end_date=merge_field(records, "end_date"),
    )