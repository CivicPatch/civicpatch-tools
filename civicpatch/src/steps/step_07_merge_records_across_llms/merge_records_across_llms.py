import json
from typing import List, Dict, TypedDict, Any
from utils import people_utils, merge_utils, data_utils
from schemas import Person, PipelineStatus, PipelineContext, MissingPerson, FieldComparison, MergeRecordsAcrossLLMsStep
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher

MINIMUM_AGREEMENT_SCORE = 80
FIELD_WEIGHTS = {
    "roles": 1.0,           
    "divisions": 0.8,       
    "email": 0.5,         
    "start_date": 0.5,      
    "end_date": 0.5,        
    "website": 0.2,        
    "phone_number": 0.2,    
}
FIELDS_TO_CHECK = list(FIELD_WEIGHTS.keys())

def merge_records_across_llms(context: PipelineContext) -> Dict[str, Any]:
    """
    Merge records across all LLMs to produce a unified list of Person objects.
    """

    # Get people_by_llm from the previous step
    people_by_llm: Dict[str, List[Person]] = context["steps"][PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value]["people_by_llm"]
    people_by_llm = {k: [Person.model_validate(p) if isinstance(p, dict) else p for p in v] for k, v in people_by_llm.items()}
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]
    state = context["state"]
    geoid = context["geoid"]
    municipality_context = data_utils.get_municipality_context(state, geoid)
    place = municipality_context.municipality_entry.name

    # Group records across LLMs based on weak ties and names
    groups_by_llm = group_records_across_llms(people_by_llm)

    # Merge each group and collect disagreements
    merged_people = []
    all_disagreements = {}  # Dict[person_name, List[FieldComparison]]
    missing_people = []

    for grouped_people_by_llm in groups_by_llm:
        # Fix: Check if the group is empty
        if not grouped_people_by_llm:
            continue
            
        # Merge the group
        merged_person = merge_group_across_llms(
            [person for llm_people in grouped_people_by_llm.values() for person in llm_people],
            state, 
            place
        )
        merged_people.append(merged_person)
        
        # Collect field-by-field disagreements for this person
        field_comparisons = collect_field_comparisons(
            merged_person,
            grouped_people_by_llm,  # Pass the grouped data directly
            FIELDS_TO_CHECK
        )
        
        # Store disagreements if any exist
        if field_comparisons:
            all_disagreements[merged_person.name] = field_comparisons
        
        # Fix: Pass the correct parameters to check_for_missing_person
        missing_person = check_for_missing_person(
            merged_person.name,
            grouped_people_by_llm,  # Pass the grouped data
            list(people_by_llm.keys())  # Pass all LLM names
        )
        if missing_person:
            missing_people.append(missing_person)

    # Calculate overall agreement score (include missing people in the calculation)
    overall_agreement_score = calculate_overall_agreement_score(
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

    # Create the final step result
    step_result = MergeRecordsAcrossLLMsStep(
        people=sorted_people,
        agreement_score=overall_agreement_score,
        disagreements=all_disagreements,
        missing_people=missing_people,
        validation_errors=validation_errors,
    )

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value: step_result.model_dump()
        }
    }

def check_for_missing_person(person_name: str, grouped_people_by_llm: Dict[str, List[Person]], all_llm_names: List[str]) -> MissingPerson:
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

def collect_field_comparisons(
    merged_person: Person,
    grouped_people_by_llm: Dict[str, List[Person]],  # This is now directly from the group
    fields: List[str]
) -> List[FieldComparison]:
    """
    Compare each llm's value against the final merged value.
    Returns only fields that have disagreements.
    """
    comparisons = []
    
    for field in fields:
        merged_value = getattr(merged_person, field)
        
        # Collect values from each llm
        llm_values = {}
        has_disagreement = False

        for llm, people in grouped_people_by_llm.items():
            if not people:
                llm_values[llm] = "(missing)"
                has_disagreement = True
                continue
            
            llm_value = getattr(people[0], field)  # Take first person (should be only one after within-LLM merge)
            if isinstance(llm_value, list):
                llm_values[llm] = ", ".join(llm_value) if llm_value else "(empty)"
            else:
                llm_values[llm] = str(llm_value) if llm_value else "(empty)"

            # Compare original values before string conversion
            if llm_value and not values_match(llm_value, merged_value):
                has_disagreement = True
        
        # Only add to comparisons if there's disagreement
        if has_disagreement:
            # Convert merged_value to string format for output
            merged_str = ", ".join(merged_value) if isinstance(merged_value, list) else (str(merged_value) if merged_value else "(empty)")
            comparisons.append(FieldComparison(
                field=field,
                merged_value=merged_str,
                llm_values=llm_values,
                disagreement_score=calculate_disagreement_score(field, merged_str, llm_values)
            ))
    
    return comparisons

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

def merge_group_across_llms(group: List[Person], state, place) -> Person:
    """
    Merge a group of weakly tied Person objects into a single Person object.
    """
    # Collect roles and divisions that appear in more than one source
    role_counter = Counter(role for person in group for role in person.roles)
    division_counter = Counter(div for person in group for div in person.divisions)

    roles = [role for role, count in role_counter.items() if count > 1]  # Include roles present in more than one source
    divisions = [div for div, count in division_counter.items() if count > 1]  # Include divisions present in more than one source

    # For single-value fields, take the most common non-empty value across all sources
    image_counter = Counter(person.image for person in group if person.image)
    phone_counter = Counter(person.phone_number for person in group if person.phone_number)
    website_counter = Counter(person.website for person in group if person.website)
    start_date_counter = Counter(person.start_date for person in group if person.start_date)
    end_date_counter = Counter(person.end_date for person in group if person.end_date)
    sources = set(
        ds
        for person in group
        if person.sources  # Check if sources exists
        for ds in person.sources  # Flatten the list of data sources
    )

    # Use the most common name in the group as the canonical name
    name_counter = Counter(person.name for person in group)
    canonical_name = name_counter.most_common(1)[0][0]

    return Person(
        name=canonical_name,
        roles=roles,
        divisions=divisions,
        image=image_counter.most_common(1)[0][0] if image_counter else "",
        cdn_image="",
        email=merge_field([person.email for person in group]),
        phone_number=merge_field([person.phone_number for person in group]),
        website=merge_field([person.website for person in group]),
        start_date=merge_field([person.start_date for person in group]),
        end_date=merge_field([person.end_date for person in group]),
        sources=sources,
        state=state, 
        place=place,
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )

def merge_field(values: List[str]) -> Any:
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
        return ""
    return most_common_value

def values_match(value1, value2):
    """Helper to compare values case-insensitively, handling both strings and lists."""
    if isinstance(value1, list) and isinstance(value2, list):
        # Convert lists to sets of lowercase strings for comparison
        set1 = {str(item).lower() for item in value1}
        set2 = {str(item).lower() for item in value2}
        return bool(set1 & set2)  # Return True if any items match
    elif isinstance(value1, str) and isinstance(value2, str):
        # Compare strings case-insensitively
        return value1.lower() == value2.lower()
    else:
        return value1 == value2

def calculate_disagreement_score(field_name: str, merged_value: str, llm_values: Dict[str, str]) -> float:
    """
    Calculate disagreement score based on field type and values.
    """
    # Skip empty or missing values
    valid_values = [v for v in llm_values.values() if v not in ["(empty)", "(missing)"]]
    if not valid_values:
        return 0.0

    # Handle list fields (roles, divisions)
    if field_name in ["roles", "divisions"]:
        if merged_value in ["", "(empty)"]:
            empty_count = sum(1 for v in llm_values.values() if v in ["", "(empty)"])
            if empty_count > 1:
                return 0.0

        value_sets = [set(v.lower().split(", ")) for v in valid_values]
        merged_set = set(merged_value.lower().split(", "))
        for value_set in value_sets:
            if value_set & merged_set:
                return 0.0
        return FIELD_WEIGHTS.get(field_name, 1.0)

    # Handle string fields
    else:
        if merged_value in ["", "(empty)"]:
            empty_count = sum(1 for v in llm_values.values() if v in ["", "(empty)"])
            if empty_count > 1:
                return 0.0

        match_count = sum(1 for v in valid_values if v.lower() == merged_value.lower())
        if match_count >= 2:
            return 0.0
        else:
            max_similarity = max(SequenceMatcher(None, v.lower(), merged_value.lower()).ratio() for v in valid_values)
            disagreement_score = 1.0 - max_similarity
            return disagreement_score * FIELD_WEIGHTS.get(field_name, 1.0)


def calculate_overall_agreement_score(
    all_disagreements: Dict[str, List[FieldComparison]],
    missing_people: List[MissingPerson],
    total_llms: int,
    total_people: int
) -> float:
    # Calculate total disagreement score
    total_disagreement = 0.0
    for person_disagreements in all_disagreements.values():
        for field_comparison in person_disagreements:
            field_weight = FIELD_WEIGHTS.get(field_comparison.field, 1.0)
            total_disagreement += field_comparison.disagreement_score * field_weight

    # Normalize disagreement score
    disagreement_weight = 0.5
    total_weight = sum(FIELD_WEIGHTS.get(field, 1.0) for field in FIELDS_TO_CHECK)
    disagreement = (total_disagreement / (total_weight * total_llms)) * disagreement_weight if total_weight > 0 else 0.0

    print("Disagreement because", disagreement)

    # Calculate missing people penalty
    missing_penalty = 0.0
    if missing_people:
        for missing_person in missing_people:
            missing_ratio = len(missing_person.missing_from_llms) / total_llms
            missing_penalty += missing_ratio
        missing_penalty = missing_penalty / total_people  # Normalize by total people
    missing_penalty = missing_penalty * (1 - disagreement_weight)  # Weight the missing penalty

    # Final score: 1 - (normalized_disagreement + missing_penalty)
    agreement_score = 1.0 - (disagreement + missing_penalty)

    # Convert to percentage and clamp between 0 and 100
    return max(0.0, min(100.0, round(agreement_score * 100, 2)))