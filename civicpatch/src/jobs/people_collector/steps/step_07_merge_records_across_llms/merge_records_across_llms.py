from typing import List, Dict, Any, cast
from utils import people_utils, merge_utils
from domain.models import Person
from jobs.people_collector.schemas import (
    PeopleCollectorContext, 
    MissingPerson,
    MergeRecordsAcrossLLMsStep, 
    MergeRecordsWithinLLMStep, ResearchMunicipalityStep
)
from collections import Counter
from datetime import datetime, timezone
from . import comparison_utils
import json

MINIMUM_AGREEMENT_SCORE = 80
FIELD_WEIGHTS = {
    "roles": 1.0,           
    "divisions": 0.8,       
    "emails": 0.5,         
    "urls": 0.2,        
    "phones": 0.2,    
    "start_date": 0.5,      
    "end_date": 0.5,        
}
FIELDS_TO_CHECK = list(FIELD_WEIGHTS.keys())

def merge_records_across_llms(context: PeopleCollectorContext) -> MergeRecordsAcrossLLMsStep:
    """
    Merge records across all LLMs to produce a unified list of Person objects.
    """
    jurisdiction_id = context.data.jurisdiction_id

    # Get people_by_llm from the previous step
    people_by_llm: Dict[str, List[Person]] = context.data.merge_records_within_llm_step.people_by_llm
    government_type = context.data.research_municipality_step.government_type 

    # Group records across LLMs based on weak ties and names
    groups_by_llm = group_records_across_llms(people_by_llm)
    
    # Merge each group and collect disagreements
    merged_people = []
    all_disagreements = {}  # Dict[person_name, List[FieldComparison]]
    missing_people = []

    for grouped_identities_by_llm in groups_by_llm:
        # Merge the group
        merged_person = merge_group_across_llms(
            [person for llm_people 
             in grouped_identities_by_llm.values() 
             for person in llm_people
             ],
            jurisdiction_id
        )

        # Skip person if no roles after merge
        if len(merged_person.roles) == 0:
            continue

        merged_people.append(merged_person)
        
        # Collect field-by-field disagreements for this person
        field_comparisons = comparison_utils.collect_field_comparisons(
            merged_person,
            grouped_identities_by_llm,  # Pass the grouped data directly
            FIELDS_TO_CHECK,
            FIELD_WEIGHTS
        )
        
        # Store disagreements if any exist
        if field_comparisons:
            all_disagreements[merged_person.name] = field_comparisons
        
        missing_person = check_for_missing_person(
            merged_person.name,
            grouped_identities_by_llm,  # Pass the grouped data
            list(people_by_llm.keys())  # Pass all LLM names
        )
        if missing_person:
            missing_people.append(missing_person)

    # Calculate overall agreement score (include missing people in the calculation)
    overall_agreement_score = comparison_utils.calculate_overall_agreement_score(
        FIELD_WEIGHTS,
        FIELDS_TO_CHECK,
        all_disagreements, 
        missing_people, 
        len(people_by_llm), 
        len(merged_people)
    )

    # Sort people by role priority, division, and name
    sorted_people = people_utils.sort_people(merged_people, government_type)

    validation_errors = []
    if overall_agreement_score < MINIMUM_AGREEMENT_SCORE:
        validation_errors.append(
            f"Overall agreement score {overall_agreement_score:.2f}% is below the minimum threshold of {MINIMUM_AGREEMENT_SCORE}%."
        )

    return MergeRecordsAcrossLLMsStep(
        people=sorted_people,
        agreement_score=overall_agreement_score,
        disagreements=all_disagreements,
        missing_people=missing_people,
        validation_errors=validation_errors,
    )


def check_for_missing_person(person_name: str, grouped_people_by_llm: Dict[str, List[Person]], all_llm_names: List[str]) -> MissingPerson | None:
    """
    Check if this person is missing from some LLMs and create MissingPerson if so.
    """
    # Remove debug print
    found_in_llms = list(grouped_people_by_llm.keys())
    missing_from_llms = [llm for llm in all_llm_names if llm not in found_in_llms]
    
    if missing_from_llms:
        return MissingPerson(
            name=person_name,
            missing_from_llms=missing_from_llms,
            found_in_llms=found_in_llms
        )
    
    return None


def group_records_across_llms(people_by_llm: Dict[str, List[Person]]) -> List[Dict[str, List[Person]]]:
    """
    Group records across LLMs based on weak ties.
    Returns a list of groups, where each group is a dict mapping LLM -> List[Person] for that identity.

    Ex:
    [
        {
            "LLM1": [PersonA_from_LLM1, PersonB_from_LLM1],
            "LLM2": [PersonA_from_LLM2]
        },
        {
            "LLM3": [PersonC_from_LLM3]
        }
    ]
    """
    # Create a list of (person, llm_source) tuples
    all_people_with_source = [
        (person, llm) 
        for llm, people in people_by_llm.items() 
        for person in people
    ]
    
    visited = set()
    groups = []

    for i, (person, llm) in enumerate(all_people_with_source):
        if i in visited:
            continue

        # Start a new group with the current person
        group = {llm: [person]}
        visited.add(i)

        # Compare with all other people
        for j, (other_person, other_llm) in enumerate(all_people_with_source):
            if j in visited:
                continue
            
            # Check if this person matches anyone already in the group
            if any(merge_utils.is_weakly_tied(existing_person, other_person) 
                   for existing_people in group.values() 
                   for existing_person in existing_people):
                
                if other_llm not in group:
                    group[other_llm] = []
                group[other_llm].append(other_person)
                visited.add(j)

        groups.append(group)

    return groups

def merge_group_across_llms(group: List[Person], jurisdiction_id: str) -> Person:
    """
    Merge a group of weakly tied Person objects into a single Person object.
    """
    # Collect roles and divisions that appear in more than one source
    role_counter = Counter(role for person in group for role in person.roles)
    division_counter = Counter(div for person in group for div in person.divisions)

    roles = [role for role, count in role_counter.items()] 
    divisions = [div for div, count in division_counter.items() if count > 1]  # Include divisions present in more than one source

    # For single-value fields, take the most common non-empty value across all sources
    image_counter = Counter(person.image for person in group if person.image)
    source_urls = set(
        ds
        for person in group
        if person.source_urls  # Check if sources exists
        for ds in person.source_urls  # Flatten the list of data sources
    )

    # Use the most common name in the group as the canonical name
    name_counter = Counter(person.name for person in group)
    canonical_name = name_counter.most_common(1)[0][0]

    return Person(
        name=canonical_name,

        email=merge_field_to_list([person.emails for person in group if person.emails]),
        phone_number=merge_field_to_list([person.phones for person in group if person.phones]),
        website=merge_field_to_list([person.urls for person in group if person.urls]),
        
        start_date=merge_field("start_date", [person.start_date for person in group if person.start_date]),
        end_date=merge_field("end_date", [person.end_date for person in group if person.end_date]),
        
        roles=roles,
        divisions=divisions,
        
        image=image_counter.most_common(1)[0][0] if image_counter else "",
        cdn_image="",

        source_urls=list(source_urls),
        jurisdiction_id=jurisdiction_id,
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )

def merge_field(field: str, values: List[str]) -> Any:
    """
    Merge a list of fields with the following criteria:
    - If all values are empty, return empty string
    - If no value has at least 2 occurrences, return empty string
    - Otherwise, return the most common non-empty value
    
    """
    non_empty_values = [v for v in values if v]
    if not non_empty_values:
        return ""

    value_counter = Counter(non_empty_values)
    most_common_value, count = value_counter.most_common(1)[0]
    if count < 2:
        if field in ["website"]:
            # For website, allow a single occurrence if it's a valid URL
            if most_common_value.startswith("http://") or most_common_value.startswith("https://"):
                return most_common_value
        return ""

    return most_common_value

def merge_field_to_list(records: List[List[str]]) -> List[str]:
    """
    Merge a multi-value field (e.g., emails, phones, urls) from a list of lists of strings.
    Collect unique values and include only those that appear in at least two records.
    """
    # Flatten the list of lists and count occurrences of each value
    all_values = [value for sublist in records for value in sublist]
    value_counter = Counter(all_values)

    # Keep only values that appear in at least two records
    merged_values = [value for value, count in value_counter.items() if count >= 2]

    return merged_values