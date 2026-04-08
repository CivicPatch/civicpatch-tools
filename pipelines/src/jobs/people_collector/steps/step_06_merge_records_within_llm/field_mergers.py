from typing import List
from jobs.people_collector.schemas import LLMPerson
from collections import Counter

def merge_roles(records: List[LLMPerson]) -> List[str]:
    unique_roles = set()
    for record in records:
        for role in record.roles:
            if role:
                unique_roles.add(role)
    return list(unique_roles)

def merge_designations(records: List[LLMPerson]) -> List[str]:
    """
    Collect a set of unique designations from all records.
    """

    unique_designations = set()
    for record in records:
        for designation in record.designations:
            if designation:
                unique_designations.add(designation)
    return list(unique_designations)

def merge_field(values: List[str]) -> str:
    """
    Merge a single-value field (start_date, end_date) from a list of LLMPerson records.
    Prefer non-empty, most frequent value.
    """
    value_counter = Counter(value for value in values if value)
    if not value_counter:
        return ""
    most_common = value_counter.most_common()
    max_count = most_common[0][1]
    tied_values = [value for value, count in most_common if count == max_count]
    if len(tied_values) == 1:
        return tied_values[0]
    # If there's a tie, return the first one (arbitrary choice)
    merged_value = tied_values[0]

    return merged_value 

def merge_field_to_list(values: List[str]) -> List[str]:
    """
    Collect a set of unique values.
    Filter out empty values.
    """
    return list(set(value for value in values if value))