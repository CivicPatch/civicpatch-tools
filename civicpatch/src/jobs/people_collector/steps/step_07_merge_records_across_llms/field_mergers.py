from typing import List, Any
from collections import Counter

def merge_field(field: str, values: List[str]) -> Any:
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
        if field in ["website"]:
            # For website, allow a single occurrence if it's a valid URL
            if most_common_value.startswith("http://") or most_common_value.startswith("https://"):
                return most_common_value
        return ""

    return most_common_value

def merge_field_to_list(records: List[List[str]]) -> List[str]:
    """
    Merge a multi-value field (e.g., emails, phones, urls) from a list of lists of strings.
    Collect unique values and include only those that appear in at least two records.
    """
    # Flatten the list of lists and count occurrences of each value
    all_values = [value for sublist in records for value in sublist]
    value_counter = Counter(all_values)

    # Keep only values that appear in at least two records
    merged_values = [value for value, count in value_counter.items() if count >= 2]

    return merged_values