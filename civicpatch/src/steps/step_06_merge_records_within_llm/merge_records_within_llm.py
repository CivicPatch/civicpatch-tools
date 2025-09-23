from typing import Dict, List
from schemas import (
    LLMPerson, Person, PipelineStatus, RecordsByLLM, PipelineContext
)
from collections import Counter
import utils.config_utils as config_utils

def merge_records_within_llm(context: PipelineContext):
    """
    Merge records within each llm to produce a unified list of Person objects.
    """

    records_by_llm: RecordsByLLM = context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value]["records_by_llm"]
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
    sources = [r.source for r in records if r.source]

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
    unique_roles = set()
    for record in records:
        for role in record.roles:
            if role:
                unique_roles.add(role)
    return list(unique_roles)

def merge_divisions(records: List[LLMPerson]) -> List[str]:
    """
    Collect a set of unique divisions from all records.
    """

    unique_divisions = set()
    for record in records:
        for division in record.divisions:
            if division:
                unique_divisions.add(division)
    return list(unique_divisions)