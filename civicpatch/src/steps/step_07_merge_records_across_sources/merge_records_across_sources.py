from typing import List, Dict, TypedDict, Any
from schemas import Person, PipelineStatus, PipelineContext, Disagreement, MissingPerson
from collections import Counter
from datetime import datetime, timezone

def merge_records_across_sources(context: PipelineContext) -> Dict[str, Any]:
    """
    Merge records across all sources to produce a unified list of Person objects.
    Uses people_by_source from the previous step (MERGE_RECORDS_WITHIN_SOURCE).
    """
    # Get people_by_source from previous step
    people_by_source: Dict[str, List[Dict]] = context["steps"][PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE.value]["people_by_source"]
    
    # Aggregate all unique names across sources
    canonical_names = set(
        Person.model_validate(person).name
        for people in people_by_source.values() 
        for person in people
    )

    # Initialize disagreements, missing_people lists, and disagreement score
    disagreements: List[Disagreement] = []
    missing_people: List[MissingPerson] = []
    total_disagreement_score = 0

    # Merge people with same canonical name across sources
    merged_people: List[Dict] = []
    num_sources = len(people_by_source)
    for canonical_name in canonical_names:
        # Collect all Person objects grouped by source for this canonical name
        grouped_people_by_source = {
            source: [
                Person.model_validate(person)
                for person in people
                if Person.model_validate(person).name == canonical_name
            ]
            for source, people in people_by_source.items()
        }
        
        # Identify missing people
        missing_sources = [
            source for source, people in grouped_people_by_source.items() if not people
        ]

        fields = ["roles", "divisions", "phone_number", "email", "website", "start_date", "end_date"]
        missing_person_multiplier = len(fields)  # Or set to a fixed value like 5
        for source in missing_sources:
            missing_people.append(MissingPerson(source=source, person_name=canonical_name))
            total_disagreement_score += missing_person_multiplier

        # Skip disagreement calculation if the person is missing from any source
        if missing_sources:
            continue

        # Merge Person objects into a single Person object
        merged_person = merge_people_across_sources(canonical_name, grouped_people_by_source)

        # Identify disagreements during merging
        for source, people in grouped_people_by_source.items():
            for person in people:
                for field in ["roles", "divisions", "phone_number", "email", "start_date", "end_date"]:
                    merged_value = getattr(merged_person, field)
                    source_value = getattr(person, field, None)
                    if source_value and source_value != merged_value:
                        # Convert list fields (roles, divisions) to comma-separated strings for Disagreement
                        if isinstance(source_value, list):
                            source_value = ", ".join(source_value)
                        if isinstance(merged_value, list):
                            merged_value = ", ".join(merged_value)
                        if source_value != merged_value:  # Only add disagreement if values truly differ
                            disagreements.append(Disagreement(
                                source=source,
                                person_name=canonical_name,
                                field=field,
                                value=source_value
                            ))
                            total_disagreement_score += 1  # Increment disagreement score

        merged_people.append(merged_person.model_dump())

    # Calculate agreement score
    fields = ["roles", "divisions", "phone_number", "email", "website", "start_date", "end_date"]
    max_possible_disagreement = num_sources * len(canonical_names) * len(fields)
    agreement_score = 100 * (1 - (total_disagreement_score / max_possible_disagreement)) if max_possible_disagreement > 0 else 100.0

    return {
        "steps": {
            **context["steps"],
            PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES.value: {
                "people": merged_people,
                "agreement_score": agreement_score,
                "disagreements": [disagreement.model_dump() for disagreement in disagreements],
                "missing_people": [missing_person.model_dump() for missing_person in missing_people]
            }
        }
    }


def merge_people_across_sources(canonical_name: str, people_by_source: Dict[str, List[Person]]) -> Person:
    """
    Merge a list of Person objects grouped by source into a single Person object.
    Only include roles and divisions that appear in more than one source.
    """
    # Collect roles and divisions that appear in more than one source
    role_counter = Counter(role for source, people in people_by_source.items() for person in people for role in person.roles)
    division_counter = Counter(div for source, people in people_by_source.items() for person in people for div in person.divisions)
    
    roles = [role for role, count in role_counter.items() if count > 1]  # Include roles present in more than one source
    divisions = [div for div, count in division_counter.items() if count > 1]  # Include divisions present in more than one source
    
    # For single-value fields, take the most common non-empty value across all sources
    image_counter = Counter(person.image for source, people in people_by_source.items() for person in people if person.image)
    phone_counter = Counter(person.phone_number for source, people in people_by_source.items() for person in people if person.phone_number)
    email_counter = Counter(person.email for source, people in people_by_source.items() for person in people if person.email)
    website_counter = Counter(person.website for source, people in people_by_source.items() for person in people if person.website)
    start_date_counter = Counter(person.start_date for source, people in people_by_source.items() for person in people if person.start_date)
    end_date_counter = Counter(person.end_date for source, people in people_by_source.items() for person in people if person.end_date)
    data_sources = set(
        ds
        for people in people_by_source.values()
        for person in people
        if person.data_sources  # Check if data_sources exists
        for ds in person.data_sources  # Flatten the list of data sources
    )

    return Person(
        name=canonical_name,
        roles=roles,
        divisions=divisions,
        image=image_counter.most_common(1)[0][0] if image_counter else "",
        cdn_image="",
        email=email_counter.most_common(1)[0][0] if email_counter else "",
        phone_number=phone_counter.most_common(1)[0][0] if phone_counter else "",
        website=website_counter.most_common(1)[0][0] if website_counter else "",
        start_date=start_date_counter.most_common(1)[0][0] if start_date_counter else "",
        end_date=end_date_counter.most_common(1)[0][0] if end_date_counter else "",
        data_sources=data_sources,
        updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds')
    )


def calculate_agreement_score(people_by_source: Dict[str, List[Person]]) -> float:
    """
    Calculate an agreement score based on the consistency of data across sources.
    Start with 100 and subtract disagreement scores for inconsistent fields.
    """
    if not people_by_source:
        return 0.0

    total_disagreement = 0
    num_sources = len(people_by_source)

    # Aggregate all people across sources
    all_people = [person for people in people_by_source.values() for person in people]

    # Check roles and divisions
    role_counter = Counter(role for person in all_people for role in person.roles)
    division_counter = Counter(div for person in all_people for div in person.divisions)

    # Add disagreement for roles/divisions not present in all sources
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
