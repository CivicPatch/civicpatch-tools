from typing import List, Dict, TypedDict, Any
from utils import people_utils, merge_utils, data_utils
from schemas import Person, PipelineStatus, PipelineContext, MissingPerson, FieldComparison
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher

MINIMUM_AGREEMENT_SCORE = 80

def merge_records_across_llms(context: PipelineContext) -> Dict[str, Any]:
    """
    Merge records across all LLMs to produce a unified list of Person objects.
    Uses people_by_llm from the previous step (MERGE_RECORDS_WITHIN_LLM).
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
    identity_groups = group_records_across_llms(people_by_llm)

    # Merge each group into a single Person object
    merged_people = [merge_group_across_llms(identity_group, government_type, state, place) for identity_group in identity_groups]

    # Sort people by role priority, division, and name
    sorted_people = people_utils.sort_people(merged_people, government_type)

    # Convert to dicts for easier processing
    sorted_people_dict = [person.model_dump() for person in sorted_people]

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value: {
                "people": sorted_people_dict
            }
        }
    }

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

def collect_field_comparisons(
    canonical_name: str,
    merged_person: Person,
    grouped_people_by_llm: Dict[str, List[Person]],
    fields: List[str]
) -> List[FieldComparison]:
    """
    Compare each llm's value against the final merged value.
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
            
            llm_value = getattr(people[0], field)
            if isinstance(llm_value, list):
                llm_values[llm] = ", ".join(llm_value) if llm_value else "(empty)"
            else:
                llm_values[llm] = llm_value if llm_value else "(empty)"

            # Compare original values before string conversion
            if llm_value and not values_match(llm_value, merged_value):
                has_disagreement = True
        
        if has_disagreement:
            # Convert merged_value to string format for output
            merged_str = ", ".join(merged_value) if isinstance(merged_value, list) else merged_value
            comparisons.append(FieldComparison(
                field=field,
                person_name=canonical_name,
                merged_value=merged_str or "(empty)",
                llm_values=llm_values,
                disagreement_score=calculate_disagreement_score(field, merged_str, llm_values)
            ))
    
    return comparisons

def calculate_disagreement_score(field_name: str, merged_value: str, llm_values: Dict[str, str]) -> float:
    """
    Calculate disagreement score based on field type and values.
    For lists (roles, divisions): if any items match, score is 0
    For strings: calculate based on string similarity
    """
    # Skip empty or missing values
    valid_values = [v for v in llm_values.values() if v not in ["(empty)", "(missing)"]]
    if not valid_values:
        return 0.0

    # Handle list fields (roles, divisions)
    if field_name in ["roles", "divisions"]:
        # If any items match across sources, no disagreement
        value_sets = [set(v.lower().split(", ")) for v in valid_values]
        merged_set = set(merged_value.lower().split(", "))
        
        # Check for any intersection between sets
        for value_set in value_sets:
            if value_set & merged_set:  # If there's any overlap
                return 0.0
        return 1.0  # Complete disagreement

    # Handle string fields
    else:
        # Calculate string similarity scores
        similarities = []
        for llm_value in valid_values:
            ratio = SequenceMatcher(None, 
                                  merged_value.lower(), 
                                  llm_value.lower()).ratio()
            similarities.append(ratio)
        
        # Average the dissimilarity (1 - similarity)
        avg_dissimilarity = 1 - (sum(similarities) / len(similarities))
        return round(avg_dissimilarity, 2)  # Round to 2 decimal places

def calculate_agreement_score(people_by_llm: Dict[str, List[Person]]) -> float:
    """
    Calculate an agreement score based on the consistency of data across llms.
    Start with 100 and subtract disagreement scores for inconsistent fields.
    """
    if not people_by_llm:
        return 0.0

    total_disagreement = 0
    num_sources = len(people_by_llm)

    # Aggregate all people across llms
    all_people = [person for people in people_by_llm.values() for person in people]

    # Check roles and divisions
    role_counter = Counter(role for person in all_people for role in person.roles)
    division_counter = Counter(div for person in all_people for div in person.divisions)

    # Add disagreement for roles/divisions not present in all llms
    total_disagreement += sum(1 for count in role_counter.values() if count < num_sources)
    total_disagreement += sum(1 for count in division_counter.values() if count < num_sources)

    # Check single-value fields
    fields = ["phone_number", "email", "website", "start_date", "end_date"]  # Optional fields included
    for field in fields:
        field_values = [
            getattr(person, field)
            for person in all_people
            if getattr(person, field)  # Only consider non-empty values
        ]
        if len(field_values) > 1 and len(set(field_values)) > 1:
            total_disagreement += 1

    # Calculate final agreement score
    max_possible_disagreement = len(all_people) * len(fields)  # Include optional fields
    if max_possible_disagreement == 0:
        return 100.0

    agreement_score = 100 * (1 - (total_disagreement / max_possible_disagreement))
    return max(0.0, min(100.0, agreement_score))

def people_with_target_roles(people: List[Person], target_roles: List[str]) -> List[Person]:
    """
    Return a list of people who have any of the target roles.
    """
    target_roles_lower = {role.lower() for role in target_roles}
    return [
        person for person in people
        if any(role.lower() in target_roles_lower for role in person.roles)
    ]

def group_records_across_llms(people_by_llm: Dict[str, List[Person]]) -> List[List[Person]]:
    """
    Group records across LLMs based on weak ties.
    Returns a list of groups, where each group is a list of Person objects that are weakly tied.
    """
    all_people = [
        person for people in people_by_llm.values() for person in people
    ]
    visited = set()
    groups = []

    for i, person in enumerate(all_people):
        if i in visited:
            continue

        # Start a new group with the current person
        group = [person]
        visited.add(i)

        # Compare the current person with all other people
        for j, other_person in enumerate(all_people):
            if j in visited:
                continue
            if any(merge_utils.is_weakly_tied(group_person, other_person) for group_person in group):
                group.append(other_person)
                visited.add(j)

        groups.append(group)

    return groups

def merge_group_across_llms(group: List[Person], government_type: str, state, place) -> Person:
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
    email_counter = Counter(person.email for person in group if person.email)
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
        roles=people_utils.normalize_roles(government_type, roles),
        divisions=people_utils.normalize_divisions(divisions),
        image=image_counter.most_common(1)[0][0] if image_counter else "",
        cdn_image="",
        email=email_counter.most_common(1)[0][0] if email_counter else "",
        phone_number=phone_counter.most_common(1)[0][0] if phone_counter else "",
        website=website_counter.most_common(1)[0][0] if website_counter else "",
        start_date=start_date_counter.most_common(1)[0][0] if start_date_counter else "",
        end_date=end_date_counter.most_common(1)[0][0] if end_date_counter else "",
        sources=sources,
        state=state, 
        place=place,
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )