from typing import Dict, List
from schemas import (
    LLMPerson, Person, PipelineStatus, RecordsBySource, PipelineContext
)
from collections import Counter
import utils.config_utils as config_utils

def merge_records_within_source(context: PipelineContext):
    """
    Merge records within each source to produce a unified list of Person objects for each source.
    """

    records_by_source: RecordsBySource = context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value]["records_by_source"]
    people_by_source: Dict[str, List[Person]] = {}
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]

    for source, people_by_name in records_by_source.items():
        merged_people: List[Person] = []

        for canonical_name, llm_people_list in people_by_name.items():
            merged_person = merge_llm_people_to_person(canonical_name, llm_people_list, government_type)
            merged_person = merged_person.model_dump()
            merged_people.append(merged_person)

        people_by_source[source] = merged_people

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE.value: {
                "people_by_source": people_by_source
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
    merged_roles = merge_roles(records, government_type)
    merged_divisions = merge_divisions(records)
    phone_number = merge_field(records, "phone_number")
    email = merge_field(records, "email")
    website = merge_field(records, "website")
    start_date = merge_field(records, "start_date")
    end_date = merge_field(records, "end_date")

    return Person(
        name=canonical_name,
        roles=merged_roles,
        divisions=merged_divisions,
        image="",  # Placeholder for image
        cdn_image="",  # Placeholder for CDN image
        email=email,
        phone_number=phone_number,
        website=website,
        start_date=start_date,
        end_date=end_date,
        data_sources=[],  # Placeholder for sources
        updated_at="",  # Placeholder for updated_at
    )


def merge_field(records: List[LLMPerson], field_name: str) -> str:
    """
    Merge a single-value field (phone, email, website, start_date, end_date) from a list of LLMPerson records.
    Prefer non-empty, most frequent, then highest confidence.
    """
    values = [
        (getattr(r, field_name).data, getattr(r, field_name).llm_confidence)
        for r in records if getattr(r, field_name) and getattr(r, field_name).data
    ]
    if not values:
        return ""
    value_counts = Counter([v[0] for v in values])
    most_common = value_counts.most_common(1)[0][0]
    candidates = [v for v in values if v[0] == most_common]
    best = max(candidates, key=lambda x: x[1])
    return best[0]


def merge_roles(records: List[LLMPerson], government_type: str) -> List[str]:
    """
    Collect all unique roles from all records and normalize them using the role alias map.
    """
    role_alias_map = config_utils.get_role_alias_map(government_type)
    seen = set()
    unique_roles = []
    for record in records:
        for role in record.roles:  # Access roles directly as attribute
            if role.data:
                normalized_role = role_alias_map.get(role.data.lower(), role.data)
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
        for division in record.divisions:  # Access divisions directly as attribute
            if division.data:
                # Normalize division using alias map
                normalized_division = None
                for alias, canonical in division_alias_map.items():
                    if division.data.lower().startswith(alias):
                        # Retain suffix and next word (e.g., "Ward 1")
                        suffix = division.data[len(alias):].strip()
                        normalized_division = f"{canonical} {suffix}" if suffix else canonical
                        break
                if not normalized_division:
                    normalized_division = division.data  # Use raw division if no match
                if normalized_division not in seen:
                    seen.add(normalized_division)
                    unique_divisions.append(normalized_division)
    return unique_divisions