from typing import List, Dict, TypedDict, Any
from utils import config_utils, data_utils
from schemas import Person, PipelineStatus, PipelineContext, MissingPerson, FieldComparison
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher

MINIMUM_AGREEMENT_SCORE = 80

def merge_records_across_llms(context: PipelineContext) -> Dict[str, Any]:
    """
    Merge records across all llms to produce a unified list of Person objects.
    Uses people_by_llm from the previous step (MERGE_RECORDS_WITHIN_LLM).
    """
    # Get people_by_llm from previous step
    people_by_llm: Dict[str, List[Dict]] = context["steps"][PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value]["people_by_llm"]

    state = context["state"]
    geoid = context["geoid"]

    municipality_context = data_utils.get_municipality_context(state, geoid)

    counties = municipality_context.municipality_entry.counties
    place = municipality_context.municipality_entry.name

    # Filter people_by_llm to only include target roles
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]

    target_roles = config_utils.get_roles_by_government_type(government_type)
    for source, people in people_by_llm.items():
        filtered_people = people_with_target_roles(
            [Person.model_validate(person) for person in people],
            target_roles
        )
        people_by_llm[source] = [person.model_dump() for person in filtered_people]

    # Aggregate all unique names across llms
    canonical_names = set(context.get("names", []))

    # Initialize disagreements, missing_people lists, and disagreement score
    missing_people: List[MissingPerson] = []
    total_disagreement_score = 0

    # Merge people with same canonical name across llms 
    merged_people: List[Dict] = []
    num_sources = len(people_by_llm)

    fields = ["roles", "divisions", "phone_number", "email", "website", "start_date", "end_date"]
    
    # Initialize disagreements as a dictionary keyed by person
    disagreements_by_person: Dict[str, List[FieldComparison]] = {}
    
    for canonical_name in canonical_names:
        # Collect all Person objects grouped by source for this canonical name
        grouped_people_by_llm = {
            source: [
                Person.model_validate(person)
                for person in people
                if Person.model_validate(person).name == canonical_name
            ]
            for source, people in people_by_llm.items()
        }
        
        # Only process if person appears in at least 2 sources
        sources_with_person = [source for source, people in grouped_people_by_llm.items() if people]
        if len(sources_with_person) < 2:
            continue

        # Now identify missing sources (only for people that appear in 2+ sources)
        missing_sources = [
            source for source, people in grouped_people_by_llm.items() if not people
        ]
        
        for source in missing_sources:
            missing_people.append(MissingPerson(name=canonical_name, missing_from_llms=missing_sources, found_in_llms=sources_with_person))

        # Merge Person objects into a single Person object
        merged_person = merge_people_across_llms(canonical_name, grouped_people_by_llm)
        merged_person.state = state
        merged_person.place = place
        merged_person.counties = counties

        # Identify disagreements during merging
        person_comparisons = collect_field_comparisons(
            canonical_name,
            merged_person,
            grouped_people_by_llm,
            fields
        )
        
        # If there are any disagreements for this person, add them to the dictionary
        if person_comparisons:
            disagreements_by_person[canonical_name] = person_comparisons
            total_disagreement_score += sum(c.disagreement_score for c in person_comparisons)

        merged_people.append(merged_person.model_dump())

    # Calculate agreement score
    max_possible_disagreement = num_sources * len(canonical_names) * len(fields)
    agreement_score = 100 * (1 - (total_disagreement_score / max_possible_disagreement)) if max_possible_disagreement > 0 else 100.0

    validation_issues = []

    if agreement_score < MINIMUM_AGREEMENT_SCORE:
        validation_issues.append(f"Low agreement score: {agreement_score:.2f}. Minimum expected is {MINIMUM_AGREEMENT_SCORE}.")

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value: {
                "people": sort_people(merged_people, government_type),
                "agreement_score": agreement_score,
                "disagreements": {
                    person_name: [
                        {
                            "field": c.field,
                            "merged_value": c.merged_value,
                            "llm_values": c.llm_values,
                            "disagreement_score": c.disagreement_score
                        }
                        for c in comparisons
                    ]
                    for person_name, comparisons in disagreements_by_person.items()
                },
                "missing_people": [missing_person.model_dump() for missing_person in missing_people],
                "validation_issues": validation_issues
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

def get_role_priority(government_type: str) -> Dict[str, int]:
    """
    Returns a mapping from role name (lowercase) to its priority/order in the config.
    Aliases are ignored; only main role names are used.
    """
    role_configs = config_utils.get_role_configs_by_government_type(government_type)
    priority = {}
    for idx, role_entry in enumerate(role_configs):
        role_name = role_entry["role"].lower()
        priority[role_name] = idx
    return priority

def sort_people(people: List[Person], government_type: str) -> List[Person]:
    """
    Sort people by role priority (from config), then division, then name.
    """
    role_priority = get_role_priority(government_type)

    def sort_key(person: Person):
        # Find the highest priority among person's roles
        priorities = [role_priority.get(role.lower(), 9999) for role in person["roles"]]
        min_priority = min(priorities) if priorities else 9999
        first_division = person["divisions"][0] if person["divisions"] else ""
        return (min_priority, first_division, person["name"])

    return sorted(people, key=sort_key)

def merge_people_across_llms(canonical_name: str, people_by_llm: Dict[str, List[Person]]) -> Person:
    """
    Merge a list of Person objects grouped by source into a single Person object.
    Only include roles and divisions that appear in more than one source.
    """
    # Collect roles and divisions that appear in more than one source
    role_counter = Counter(role for source, people in people_by_llm.items() for person in people for role in person.roles)
    division_counter = Counter(div for source, people in people_by_llm.items() for person in people for div in person.divisions)
    
    roles = [role for role, count in role_counter.items() if count > 1]  # Include roles present in more than one source
    divisions = [div for div, count in division_counter.items() if count > 1]  # Include divisions present in more than one source
    
    # For single-value fields, take the most common non-empty value across all sources
    image_counter = Counter(person.image for source, people in people_by_llm.items() for person in people if person.image)
    phone_counter = Counter(person.phone_number for source, people in people_by_llm.items() for person in people if person.phone_number)
    email_counter = Counter(person.email for source, people in people_by_llm.items() for person in people if person.email)
    website_counter = Counter(person.website for source, people in people_by_llm.items() for person in people if person.website)
    start_date_counter = Counter(person.start_date for source, people in people_by_llm.items() for person in people if person.start_date)
    end_date_counter = Counter(person.end_date for source, people in people_by_llm.items() for person in people if person.end_date)
    sources = set(
        ds
        for people in people_by_llm.values()
        for person in people
        if person.sources  # Check if sources exists
        for ds in person.sources  # Flatten the list of data sources
    )

    return Person(
        name=canonical_name,
        roles=[format_role(role) for role in roles],
        divisions=[format_division(div) for div in divisions],
        image=image_counter.most_common(1)[0][0] if image_counter else "",
        cdn_image="",
        email=email_counter.most_common(1)[0][0] if email_counter else "",
        phone_number=phone_counter.most_common(1)[0][0] if phone_counter else "",
        website=website_counter.most_common(1)[0][0] if website_counter else "",
        start_date=start_date_counter.most_common(1)[0][0] if start_date_counter else "",
        end_date=end_date_counter.most_common(1)[0][0] if end_date_counter else "",
        sources=sources,
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )

def format_role(role: str) -> str:
    """
    Format a role string to have each word capitalized.
    """
    return " ".join(word.capitalize() for word in role.split())

def format_division(division: str) -> str:
    """
    Format a division string to have each word capitalized.
    """
    return " ".join(word.capitalize() for word in division.split())

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
