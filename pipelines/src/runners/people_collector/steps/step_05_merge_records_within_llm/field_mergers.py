from collections import Counter
from typing import List

from runners.people_collector.schemas import PersonRecord


def merge_labels(records: List[PersonRecord]) -> List[str]:
    """Unique raw labels across records — one per office the person was seen holding."""
    unique_labels = set()
    for record in records:
        if record.label:
            unique_labels.add(record.label)
    return list(unique_labels)


def merge_field(values: List[str]) -> str:
    """
    Merge a single-value field (start_date, end_date) from a list of PersonRecord records.
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
