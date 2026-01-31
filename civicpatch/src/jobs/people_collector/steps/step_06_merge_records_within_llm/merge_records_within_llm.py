from typing import Dict, List, cast
from jobs.people_collector.schemas import (
    LLMPerson, Person, 
    RecordsByLLM, PeopleCollectorContext, MergeRecordsWithinLLMStep,
)
from utils import merge_utils
import jobs.people_collector.steps.step_06_merge_records_within_llm.field_mergers as field_mergers
from collections import Counter
from datetime import datetime, timezone

def merge_records_within_llm(context: PeopleCollectorContext) -> MergeRecordsWithinLLMStep:
    """
    Consolidate records within each LLM to produce a unified list of Person objects.
    """
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    records_by_llm: RecordsByLLM = context.data.process_page_content_step.records_by_llm
    records_by_llm = { k: {name: [LLMPerson.model_validate(p) if isinstance(p, dict) else p for p in v] for name, v in people.items()} for k, people in records_by_llm.items() } if isinstance(records_by_llm, dict) else records_by_llm

    # Flatten the records so that we can later group by last name 
    # and merge weakly tied records
    flattened_records_by_llm = {
        llm: [person for people in people_by_name.values() for person in people] 
                for llm, people_by_name in records_by_llm.items()
    }

    people_by_llm: Dict[str, List[Person]] = {}

    for llm, records in flattened_records_by_llm.items():
        merged_people: List[Person] = []
        groups_by_last_name = group_by_last_name(records)

        for llm_records_list in groups_by_last_name.values():
            research_identities = {official.name: [official.name] for official in context.data.research_municipality_step.elected_officials}
            identity_names = context.data.config.identities or research_identities
            consolidated_people = merge_records(identity_names, llm_records_list, jurisdiction_ocdid)
            merged_people.extend(consolidated_people)

        people_by_llm[llm] = merged_people

    # Format to dict
    return MergeRecordsWithinLLMStep(people_by_llm=people_by_llm)

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

def get_source_urls(person_records: list, person: Person) -> list:
    """
    For each unique value in the merged fields, include the source_url of the record that contributed it.
    Only one source_url per unique value, tiebreaking by first record.
    """
    field_map = [
        ('roles', 'roles'),
        # ('divisions', 'divisions'),
        ('phones', 'phone'),
        ('emails', 'email'),
        # ('urls', 'url'), 
    ]
    merged_values = {plural: set(getattr(person, plural)) for plural, _ in field_map}
    source_urls = set()

    for plural, singular in field_map:
        for value in merged_values[plural]:
            for record in person_records:
                record_values = getattr(record, singular)
                values = set(record_values) if isinstance(record_values, list) else {record_values}
                if value in values:
                    url = getattr(record, "source_url", None)
                    if url:
                        source_urls.add(url)
                    break  # Tiebreak: only the first record that contributed this value

    return list(source_urls)

def merge_llm_people_to_person(canonical_name: str, llm_people_list: List[LLMPerson], jurisdiction_ocdid: str) -> Person:
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
    image = field_mergers.merge_field([r.image for r in records])
    merged_roles = field_mergers.merge_roles(records)
    merged_designations = field_mergers.merge_designations(records)
    phones = field_mergers.merge_field_to_list([r.phone for r in records])
    emails = field_mergers.merge_field_to_list([r.email for r in records])
    urls = field_mergers.merge_field_to_list([r.url for r in records])
    start_date = field_mergers.merge_field([r.start_date for r in records])
    end_date = field_mergers.merge_field([r.end_date for r in records])

    # Collect all unique names from the group, excluding the canonical name
    other_names = list(set(
        person.name for person in llm_people_list if person.name and person.name != canonical_name
    ))

    person = Person(
        name=canonical_name,
        other_names=other_names,  # Add other names here
        roles=merged_roles,
        designations=merged_designations,

        phones=phones,
        emails=emails,
        urls=urls,
        start_date=start_date,
        end_date=end_date,
        
        image=image,  # Placeholder for image
        cdn_image="",  # Placeholder for CDN image
        jurisdiction_ocdid=jurisdiction_ocdid,
        updated_at="",  # Placeholder for updated_at
        source_urls=[], # Placeholder, this gets calculated in the next few lines
    )

    source_urls = get_source_urls(llm_people_list, person)
    person.source_urls = source_urls
    return person

def merge_records(identity_names: Dict[str, List[str]], llm_people_list: List[LLMPerson], jurisdiction_ocdid: str) -> List[Person]:
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

            # Check for exact name match or weak tie
            is_exact_match = merge_utils.same_name(record.name, other_record.name)
            is_alias_match = (
                record.name in identity_names and 
                other_record.name in identity_names[record.name]
            )
            is_weak_tie = any(
                merge_utils.is_weakly_tied(identity_names, group_record, other_record) 
                for group_record in group
            )

            if is_exact_match or is_alias_match or is_weak_tie:
                group.append(other_record)
                visited.add(j)

        # Determine canonical name
        canonical_name = determine_canonical_name(identity_names, group)

        # Merge all records in the group into a single Person object
        merged_person = merge_llm_people_to_person(canonical_name, group, jurisdiction_ocdid)

        # Update other_names for weak ties
        all_names = set(person.name for person in group if person.name)  # Add all person names
        all_names.discard(canonical_name)  # Remove the canonical name from other_names
        merged_person.other_names = list(all_names)

        consolidated_groups.append(merged_person)

    return consolidated_groups

def determine_canonical_name(identity_names: Dict[str, List[str]], group: List[LLMPerson]) -> str:
    """
    Determine the canonical name for a group of LLMPerson objects.

    Priority:
    1. If a name exists in the identity_names mapping, use the canonical name from the mapping.
    2. If no name exists in the identity_names mapping, use the most frequently used name in the group.
    """
    # Count the occurrences of each name in the group
    name_counter = Counter(person.name for person in group if person.name)

    # Check if any name in the group matches a canonical name in identity_names
    for person in group:
        if person.name in identity_names:
            return person.name  # Return the canonical name from the mapping

    # Handle case where no names are found in the group
    if not name_counter:
        raise ValueError("Cannot determine canonical name for an empty group or group with no valid names.")

    # Default to the most common name if no canonical name is found
    most_common_name, _ = name_counter.most_common(1)[0]
    return most_common_name