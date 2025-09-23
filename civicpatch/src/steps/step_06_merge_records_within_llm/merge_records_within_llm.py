from typing import Dict, List
from schemas import (
    LLMPerson, Person, PipelineStatus, RecordsByLLM, PipelineContext
)
from collections import Counter
from utils import merge_utils, people_utils
import phonenumbers

def merge_records_within_llm(context: PipelineContext):
    """
    Consolidate records within each LLM to produce a unified list of Person objects.
    """
    records_by_llm: RecordsByLLM = context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value]["records_by_llm"]
    records_by_llm = { k: {name: [LLMPerson.model_validate(p) if isinstance(p, dict) else p for p in v] for name, v in people.items()} for k, people in records_by_llm.items() } if isinstance(records_by_llm, dict) else records_by_llm
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]

    # Flatten the records so that we can later group by last name 
    # and merge weakly tied records
    flattened_records_by_llm = {llm: [person for people in people_by_name.values() for person in people] for llm, people_by_name in records_by_llm.items()}
    # Then, normalize the records for comparison
    formatted_records_by_llm = {llm: [normalize_record(person, government_type) for person in people] for llm, people in flattened_records_by_llm.items()}

    people_by_llm: Dict[str, List[Person]] = {}

    for llm, records in formatted_records_by_llm.items():
        merged_people: List[Person] = []
        groups_by_last_name = group_by_last_name(records)

        for llm_records_list in groups_by_last_name.values():
            consolidated_people = merge_records(llm_records_list, government_type)
            merged_people.extend(consolidated_people)

        people_by_llm[llm] = merged_people

    # Format to dict
    people_by_llm = {k: [person.model_dump() for person in v] for k, v in people_by_llm.items()}

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value: {
                "people_by_llm": people_by_llm
            }
        }
    }

def normalize_record(record: LLMPerson, government_type: str) -> LLMPerson:
    """
    Normalize roles and divisions in an LLMPerson record.
    """
    normalized_roles = people_utils.normalize_roles(government_type, record.roles)
    normalized_divisions = people_utils.normalize_divisions(record.divisions)

    try:
        phone_number = phonenumbers.parse(record.phone_number, "US") if record.phone_number else None
        normalized_phone_number = phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.NATIONAL) if phone_number and phonenumbers.is_valid_number(phone_number) else None
    except:
        normalized_phone_number = None

    return LLMPerson(
        name=record.name,
        roles=normalized_roles,
        divisions=normalized_divisions,
        phone_number=normalized_phone_number,
        email=record.email,
        website=record.website,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source=record.source
    )

def group_by_last_name(llm_people_list: List[LLMPerson]) -> Dict[str, List[LLMPerson]]:
    """
    Group LLMPerson records by their surnames.
    """
    last_name_groups: Dict[str, List[LLMPerson]] = {}
    for person in llm_people_list:
        last_name = merge_utils.last_name(person.name)
        if last_name not in last_name_groups:
            last_name_groups[last_name] = []
        last_name_groups[last_name].append(person)
    return last_name_groups

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
    merged_roles = merge_roles(records)
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

    If there's a tie, prefer the value that contains either the first name or last name of the person.
    """
    values = [
        getattr(r, field_name)
        for r in records if getattr(r, field_name)
    ]
    if not values:
        return ""
    value_counts = Counter(values)
    most_common = value_counts.most_common(1)[0][0]
    merged_value = most_common

    # If there's a tie, prefer the value that contains either the first name or last name of the person
    if len(value_counts) > 1:
        top_count = value_counts.most_common(1)[0][1]
        tied_values = [val for val, count in value_counts.items() if count == top_count]
        if len(tied_values) > 1:
            first_name = merge_utils.first_name(records[0].name).lower()
            last_name = merge_utils.last_name(records[0].name).lower()
            for val in tied_values:
                if first_name in val.lower() or last_name in val.lower():
                    merged_value = val
                    break
    return merged_value 


def merge_roles(records: List[LLMPerson]) -> List[str]:
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

def merge_records(llm_people_list: List[LLMPerson], government_type: str) -> List[Person]:
    """
    Consolidate records within a single group of LLMPerson objects.
    Merge records that are weakly tied into unified Person objects.
    """
    consolidated_groups = []  # To store groups of weakly tied records
    visited = set()  # To track processed records

    for i, record in enumerate(llm_people_list):
        if i in visited:
            continue  # Skip already processed records

        # Start a new group with the current record
        group = [record]
        visited.add(i)

        # Compare the current record with all other records
        for j, other_record in enumerate(llm_people_list):
            if j in visited:
                continue
            if (
                merge_utils.same_name(record, other_record) or 
                any(merge_utils.is_weakly_tied(group_record, other_record) for group_record in group)
            ):
                group.append(other_record)
                visited.add(j)

        # Merge all records in the group into a single Person object
        consolidated_groups.append(merge_llm_people_to_person(group[0].name, group, government_type))

    return consolidated_groups