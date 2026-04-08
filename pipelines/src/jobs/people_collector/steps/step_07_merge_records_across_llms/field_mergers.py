from typing import List, Any
from collections import Counter

def merge_field(field: str, values: List[str]) -> Any:
    """
    Merge a list of fields with the following criteria:
    - If all values are empty, return empty string
    - Otherwise, return the most common non-empty value
    """
    non_empty_values = [v for v in values if v]
    if not non_empty_values:
        return ""

    value_counter = Counter(non_empty_values)
    most_common_value, _count = value_counter.most_common(1)[0]

    return most_common_value

def merge_field_to_list(records: List[List[str]]) -> List[str]:
    """
    Merge a multi-value field (e.g., emails, phones, urls) from a list of lists of strings.
    Collect unique values and, if there are values that appear in multiple records, include only those.
    If there are no duplicate records, include all of the unique values.
    De-duplicate the values.
    Case-insensitive: "A@B.com" and "a@b.com" are treated as the same.
    """
    value_counter = Counter(value.lower() for record in records for value in record if value)
    merged_values = [value for value, count in value_counter.items() if count > 1]  # Include values that appear in multiple records
    if not merged_values:  # If no values appear in multiple records, include all unique values
        merged_values = list(set(value.lower() for record in records for value in record if value))

    merged_values = list(dict.fromkeys(merged_values))  # De-duplicate while preserving order
    return merged_values