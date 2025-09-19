from typing import Dict, List
from schemas import (
    LLMPerson, Person, PipelineStatus, RecordsBySource, PipelineContext
)
from collections import Counter
import utils.config_utils as config_utils

def merge_records_within_llm(context: PipelineContext):
    """
    Merge records within each llm to produce a unified list of Person objects.
    """

    records_by_llm: RecordsBySource = context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value]["records_by_llm"]
    people_by_llm: Dict[str, List[Person]] = {}
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]

    for source, people_by_name in records_by_llm.items():
        merged_people: List[Person] = []

        for canonical_name, llm_people_list in people_by_name.items():
            merged_person = merge_llm_people_to_person(canonical_name, llm_people_list, government_type)
            merged_person = merged_person.model_dump()

            # Only include merged person if they have roles
            if merged_person["roles"]:
                merged_people.append(merged_person)

        people_by_llm[source] = merged_people

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value: {
                "people_by_llm": people_by_llm
            }
        }
    }


def merge_llm_people_to_person(canonical_name: str, llm_people_list: List[LLMPerson], government_type: str) -> Person:
    """
    Merge a list of LLMPerson objects into a single Person object.
    Handles both Pydantic models and dictionary inputs.
    """
    # Convert all records to LLMPerson if they're dictionaries
    records = [
        LLMPerson.model_validate(r) if isinstance(r, dict) else r 
        for r in llm_people_list
    ]
    
    # Use helper functions to merge fields
    image = merge_field(records, "image")
    merged_roles = merge_roles(records, government_type)
    merged_divisions = merge_divisions(records)
    phone_number = merge_field(records, "phone_number")
    email = merge_field(records, "email")
    website = merge_field(records, "website")
    start_date = merge_field(records, "start_date")
    end_date = merge_field(records, "end_date")
    sources = [r.data_source for r in records if r.data_source]

    return Person(
        name=canonical_name,
        roles=merged_roles,
        divisions=merged_divisions,
        image=image,  # Placeholder for image
        cdn_image="",  # Placeholder for CDN image
        email=email,
        phone_number=phone_number,
        website=website,
        start_date=start_date,
        end_date=end_date,
        sources=sources,
        updated_at="",  # Placeholder for updated_at
    )


def merge_field(records: List[LLMPerson], field_name: str) -> str:
    """
    Merge a single-value field (phone, email, website, start_date, end_date) from a list of LLMPerson records.
    Prefer non-empty, most frequent value.
    """
    values = [
        getattr(r, field_name)
        for r in records if getattr(r, field_name)
    ]
    if not values:
        return ""
    value_counts = Counter(values)
    most_common = value_counts.most_common(1)[0][0]
    return most_common


def merge_roles(records: List[LLMPerson], government_type: str) -> List[str]:
    """
    Collect roles from all records, but only include those that can be normalized
    using the role alias map. This ensures we only keep roles that match our 
    expected set of roles for the given government type.
    """
    role_alias_map = config_utils.get_role_alias_map(government_type)
    seen = set()
    unique_roles = []
    for record in records:
        for role in record.roles:
            if role and role.lower() in role_alias_map:  # Only process roles found in map
                normalized_role = role_alias_map[role.lower()]
                if normalized_role not in seen:
                    seen.add(normalized_role)
                    unique_roles.append(normalized_role)
    return unique_roles


def merge_divisions(records: List[LLMPerson]) -> List[str]:
    """
    Collect all unique divisions from all records and normalize them using the division alias map.
    For divisions, retain the suffix and the next word (e.g., "Ward 1").
    """
    division_alias_map = config_utils.get_division_alias_map()
    seen = set()
    unique_divisions = []
    for record in records:
        for division in record.divisions:
            if division:
                normalized_division = None
                for alias, canonical in division_alias_map.items():
                    if division.lower().startswith(alias):
                        suffix = division[len(alias):].strip()
                        normalized_division = f"{canonical} {suffix}" if suffix else canonical
                        break
                if not normalized_division:
                    normalized_division = division
                if normalized_division not in seen:
                    seen.add(normalized_division)
                    unique_divisions.append(normalized_division)
    return unique_divisions