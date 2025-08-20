from typing import List, Dict
from schemas import PeopleArrayLLMResponseSchema, LLMPerson

def merge_matching_people(people: List[LLMPerson]) -> List[LLMPerson]:
    """
    Merge people records with matching names, preferring non-empty fields.
    """
    people_by_name: Dict[str, LLMPerson] = {}
    
    for person in people:
        if person.name in people_by_name:
            # Merge with existing record
            existing = people_by_name[person.name]
            merged = LLMPerson(
                name=person.name,
                image=person.image or existing.image,
                roles=list(set(existing.roles + person.roles)),
                divisions=list(set(existing.divisions + person.divisions)),
                phone_number=person.phone_number or existing.phone_number,
                email=person.email or existing.email,
                website=person.website or existing.website,
                start_date=person.start_date or existing.start_date,
                end_date=person.end_date or existing.end_date,
            )
            people_by_name[person.name] = merged
        else:
            # New person
            people_by_name[person.name] = person
    
    return list(people_by_name.values())

def combine_people_results(responses: List[PeopleArrayLLMResponseSchema]) -> PeopleArrayLLMResponseSchema:
    """
    Combine results from multiple LLM responses into a single list of people.
    """
    combined_people = []
    for response in responses:
        if isinstance(response, dict):
            response = PeopleArrayLLMResponseSchema.model_validate(response)
        if response.people:
            combined_people.extend(response.people)

    # Merge people with matching names
    merged_people = merge_matching_people(combined_people)

    return PeopleArrayLLMResponseSchema(
        people=merged_people,
        thought="Combined results from multiple LLM responses."
    )
