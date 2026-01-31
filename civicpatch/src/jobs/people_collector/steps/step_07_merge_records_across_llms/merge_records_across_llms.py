from typing import List, Dict, Any, cast
from utils import people_utils, merge_utils
from domain.models import Person
from jobs.people_collector.schemas import (
    PeopleCollectorContext, 
    MissingPerson,
    MergeRecordsAcrossLLMsStep, 
)
from collections import Counter
from datetime import datetime, timezone
import jobs.people_collector.steps.step_07_merge_records_across_llms.field_mergers as field_mergers
import jobs.people_collector.steps.step_07_merge_records_across_llms.record_comparison as record_comparison

MINIMUM_AGREEMENT_SCORE = 80
FIELD_WEIGHTS = {
    "roles": 1.0,           
    "designations": 0.8,       
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
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    # Get people_by_llm from the previous step
    people_by_llm: Dict[str, List[Person]] = context.data.merge_records_within_llm_step.people_by_llm
    government_type = context.data.research_municipality_step.government_type 

    # Group records across LLMs based on weak ties and names
    research_identities = {official.name: [official.name] for official in context.data.research_municipality_step.elected_officials}
    identity_names = context.data.config.identities or research_identities
    groups_by_llm = group_records_across_llms(identity_names, people_by_llm)

    # Filter out groups that only have one LLM source
    groups_by_llm = [group for group in groups_by_llm if len(group) > 1]
    
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
            jurisdiction_ocdid
        )

        # Skip person if no roles after merge
        if len(merged_person.roles) == 0:
            continue

        merged_people.append(merged_person)
        
        # Collect field-by-field disagreements for this person
        field_comparisons = record_comparison.collect_field_comparisons(
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
    overall_agreement_score = record_comparison.calculate_overall_agreement_score(
        FIELD_WEIGHTS,
        FIELDS_TO_CHECK,
        all_disagreements, 
        missing_people, 
        len(people_by_llm), 
        len(merged_people)
    )

    # Sort people by role priority, designations, and name
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

def group_records_across_llms(identity_names: Dict[str, List[str]], people_by_llm: Dict[str, List[Person]]) -> List[Dict[str, List[Person]]]:
    """
    Group records across LLMs based on exact name match and weak ties.
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
    
    if not all_people_with_source:
        return []
    
    visited = set()
    groups = []
    
    for i, (person, llm) in enumerate(all_people_with_source):
        if i in visited:
            continue
        
        # Start a new group with the current person
        group = {llm: [person]}
        visited.add(i)
        
        # Use a queue to handle transitive grouping
        # (if A matches B and B matches C, then A, B, C should all be in one group)
        to_check = [(person, llm)]
        checked = set()
        
        while to_check:
            current_person, current_llm = to_check.pop(0)
            if id(current_person) in checked:
                continue
            checked.add(id(current_person))
            
            # Compare with all other people
            for j, (other_person, other_llm) in enumerate(all_people_with_source):
                if j in visited:
                    continue
                
                # Check for exact name match OR weak tie
                is_exact_match = (
                    current_person.name and other_person.name and 
                    current_person.name == other_person.name
                )
                is_alias_match = (
                    current_person.name in identity_names and 
                    other_person.name in identity_names[current_person.name]
                )
                is_weak_tie = merge_utils.is_weakly_tied(identity_names, current_person, other_person)
                
                if is_exact_match or is_alias_match or is_weak_tie:
                    if other_llm not in group:
                        group[other_llm] = []
                    group[other_llm].append(other_person)
                    visited.add(j)
                    to_check.append((other_person, other_llm))
                    
                    # Update other_names for weak ties
                    if is_weak_tie:
                        if not current_person.other_names:
                            current_person.other_names = []
                        if other_person.name not in current_person.other_names:
                            current_person.other_names.append(other_person.name)
        
        groups.append(group)
    
    return groups

def merge_group_across_llms(group: List[Person], jurisdiction_ocdid: str) -> Person:
    """
    Merge a group of weakly tied Person objects into a single Person object.
    """
    # Collect roles and designations that appear in more than one source
    role_counter = Counter(role for person in group for role in person.roles)
    designation_counter = Counter(div for person in group for div in person.designations)

    roles = [role for role, count in role_counter.items()] 
    designations = [div for div, count in designation_counter.items() if count > 1]  # Include designations present in more than one source

    # For single-value fields, take the most common non-empty value across all sources
    image_counter = Counter(person.image for person in group if person.image)
    source_urls = set(
        ds
        for person in group
        if person.source_urls  # Check if sources exist
        for ds in person.source_urls  # Flatten the list of data sources
    )

    # Determine canonical name
    name_counter = Counter(person.name for person in group)
    canonical_name = name_counter.most_common(1)[0][0]

    # Combine person.name and other_names into a single list, ensuring no duplicates
    all_names = set(person.name for person in group if person.name)  # Add all person names
    for person in group:
        if person.other_names:
            all_names.update(person.other_names)  # Add other_names
    all_names.discard(canonical_name)  # Remove the canonical name from other_names
    other_names = list(all_names)

    person = Person(
        name=canonical_name,
        other_names=other_names,

        roles=roles,
        designations=designations,

        emails=field_mergers.merge_field_to_list([person.emails for person in group if person.emails]),
        phones=field_mergers.merge_field_to_list([person.phones for person in group if person.phones]),
        urls=merge_urls([person.urls for person in group if person.urls]),

        start_date=field_mergers.merge_field("start_date", [person.start_date for person in group if person.start_date]),
        end_date=field_mergers.merge_field("end_date", [person.end_date for person in group if person.end_date]),

        image=image_counter.most_common(1)[0][0] if image_counter else "",
        cdn_image="",

        jurisdiction_ocdid=jurisdiction_ocdid,
        source_urls=source_urls,
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )

    return person

def merge_urls(url_groups: List[List[str]]) -> List[str]:
    """
    Priority 1: Merge list of URLs, preferring those that appear in multiple sources.
    Priority 2: If no duplicates, return at least one URL.
    """
    url_counter = Counter(url for urls in url_groups for url in urls)
    if not url_counter:
        return []
    
    # Get URLs that appear in more than one source
    merged_urls = [url for url, count in url_counter.items() if count > 1]
    
    # If no URLs appear in multiple sources, return at least one URL
    if not merged_urls:
        most_common_url, _ = url_counter.most_common(1)[0]
        merged_urls.append(most_common_url)
    
    return merged_urls