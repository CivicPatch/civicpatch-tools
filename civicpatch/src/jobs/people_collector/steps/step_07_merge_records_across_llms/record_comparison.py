from typing import Dict, List

from domain.models import Person
from jobs.people_collector.schemas import FieldComparison, MissingPerson 
from difflib import SequenceMatcher

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

def calculate_disagreement_score(
        field_weights, 
        field_name: str, 
        merged_value: str, 
        llm_values: Dict[str, str]) -> float:
    """
    Calculate disagreement score based on field type and values.
    """
    # Skip empty or missing values
    valid_values = [v for v in llm_values.values() if v not in ["(empty)", "(missing)"]]
    if not valid_values:
        return 0.0

    # Handle list fields (roles, designations)
    if field_name in ["roles", "designations"]:
        if merged_value in ["", "(empty)"]:
            empty_count = sum(1 for v in llm_values.values() if v in ["", "(empty)"])
            if empty_count > 1:
                return 0.0

        value_sets = [set(v.lower().split(", ")) for v in valid_values]
        merged_set = set(merged_value.lower().split(", "))
        for value_set in value_sets:
            if value_set & merged_set:
                return 0.0
        return field_weights.get(field_name, 1.0)

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
            return disagreement_score * field_weights.get(field_name, 1.0)


def calculate_overall_agreement_score(
    field_weights: Dict[str, float],
    fields_to_check: List[str],
    all_disagreements: Dict[str, List[FieldComparison]],
    missing_people: List[MissingPerson],
    total_llms: int,
    total_people: int
) -> float:
    # Calculate total disagreement score
    total_disagreement = 0.0
    for person_disagreements in all_disagreements.values():
        for field_comparison in person_disagreements:
            field_weight = field_weights.get(field_comparison.field, 1.0)
            total_disagreement += field_comparison.disagreement_score * field_weight

    # Normalize disagreement score
    disagreement_weight = 0.5
    total_weight = sum(field_weights.get(field, 1.0) for field in fields_to_check)
    disagreement = (total_disagreement / (total_weight * total_llms)) * disagreement_weight if total_weight > 0 else 0.0

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

def collect_field_comparisons(
    merged_person: Person,
    grouped_people_by_llm: Dict[str, List[Person]],  # This is now directly from the group
    fields: List[str],
    field_weights: Dict[str, float]
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
                disagreement_score=calculate_disagreement_score(
                    field_weights,
                    field, 
                    merged_str, 
                    llm_values)
            ))
    
    return comparisons