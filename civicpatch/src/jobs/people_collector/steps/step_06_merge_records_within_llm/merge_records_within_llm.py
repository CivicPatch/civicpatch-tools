from typing import Dict, List, cast
from jobs.people_collector.schemas import (
    LLMPerson, Person, 
    RecordsByLLM, PeopleCollectorContext, MergeRecordsWithinLLMStep,
)
from utils import merge_utils
import jobs.people_collector.steps.step_06_merge_records_within_llm.field_mergers as field_mergers

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
            consolidated_people = merge_records(llm_records_list, jurisdiction_ocdid)
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
        # ('divisions', 'divisions'), # Uncomment if you want divisions
        ('phones', 'phone'),
        ('emails', 'email'),
        # ('urls', 'url'), # Uncomment if you want urls
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
    merged_divisions = field_mergers.merge_divisions(records)
    phones = field_mergers.merge_field_to_list([r.phone for r in records])
    emails = field_mergers.merge_field_to_list([r.email for r in records])
    urls = field_mergers.merge_field_to_list([r.url for r in records])
    start_date = field_mergers.merge_field([r.start_date for r in records])
    end_date = field_mergers.merge_field([r.end_date for r in records])

    person = Person(
        name=canonical_name,
        roles=merged_roles,
        divisions=merged_divisions,

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

def merge_records(llm_people_list: List[LLMPerson], jurisdiction_ocdid: str) -> List[Person]:
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
                merge_utils.same_name(record.name, other_record.name) or 
                any(merge_utils.is_weakly_tied(group_record, other_record) for group_record in group)
            ):
                group.append(other_record)
                visited.add(j)

        # Merge all records in the group into a single Person object
        consolidated_groups.append(merge_llm_people_to_person(group[0].name, group, jurisdiction_ocdid))

    return consolidated_groups