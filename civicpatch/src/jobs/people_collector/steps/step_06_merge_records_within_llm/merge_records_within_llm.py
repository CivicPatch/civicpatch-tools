from typing import Dict, List, Optional, cast
from collections import defaultdict, Counter
from jobs.people_collector.schemas import (
    LLMPerson, Person, 
    RecordsByLLM, PeopleCollectorContext, MergeRecordsWithinLLMStep,
)
from utils import role_utils
from shared.utils import config_utils, name_utils
import jobs.people_collector.steps.step_06_merge_records_within_llm.field_mergers as field_mergers


def merge_records_within_llm(context: PeopleCollectorContext) -> MergeRecordsWithinLLMStep:
    """
    Consolidate records within each LLM to produce a unified list of Person objects.
    """
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    records_by_llm: RecordsByLLM = context.data.process_page_content_step.records_by_llm
    records_by_llm = {
        k: {
            name: [LLMPerson.model_validate(p) if isinstance(p, dict) else p for p in v]
            for name, v in people.items()
        }
        for k, people in records_by_llm.items()
    } if isinstance(records_by_llm, dict) else records_by_llm

    identities = context.data.prepare_pipeline_step.identities

    # Flatten records per LLM
    flattened_records_by_llm = {
        llm: [person for people in people_by_name.values() for person in people]
        for llm, people_by_name in records_by_llm.items()
    }

    people_by_llm: Dict[str, List[Person]] = {}

    for llm, records in flattened_records_by_llm.items():
        # Use name_utils to map every record's name to a canonical name
        canonical_map = name_utils.build_canonical_map(
            [{"name": r.name} for r in records],
            identities
        )

        # Group records by canonical name
        groups: Dict[str, List[LLMPerson]] = defaultdict(list)
        for record in records:
            canonical = canonical_map.get(record.name, record.name)
            groups[canonical].append(record)

        # Merge each group into a Person
        merged_people: List[Person] = []
        for canonical_name, group in groups.items():
            merged_person = merge_llm_people_to_person(canonical_name, group, jurisdiction_ocdid)

            all_names = set(person.name for person in group if person.name)
            all_names.discard(canonical_name)
            merged_person.other_names = list(all_names)
            merged_person.source_urls = get_source_urls(group, merged_person)

            merged_people.append(merged_person)

        # Filter out records by the roles we want to keep
        roles_to_keep = config_utils.get_role_names()
        merged_people = role_utils.people_with_roles(merged_people, roles_to_keep)

        people_by_llm[llm] = merged_people

    return MergeRecordsWithinLLMStep(people_by_llm=people_by_llm)


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
