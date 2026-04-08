
from jobs.people_collector.schemas import RawLLMPerson
from typing import List
from utils.merge_utils import same_name

def compare_people_by_name(
    people_found: List[RawLLMPerson],
    expected_people: List[RawLLMPerson],
    ignore_fields: List[str] = None,
):
    """Helper to compare two lists of people by name, ignoring order, fields, and case.
    For list fields, passes if at least one expected item is present in found record (case-insensitive for strings).
    """
    if ignore_fields is None:
        ignore_fields = []

    def normalize(val):
        if isinstance(val, str):
            return val.lower()
        if isinstance(val, list):
            return [normalize(v) for v in val]
        return val

    found_dict = {person.name.lower(): person for person in people_found}
    expected_dict = {person.name.lower(): person for person in expected_people}

    found_names = set(found_dict.keys())
    expected_names = set(expected_dict.keys())
    for expected_name in expected_names:
        if not any(same_name(expected_name, found_name) for found_name in found_names):
            assert False, f"Expected person not found: {expected_name}"
    for found_name in found_names:
        if not any(same_name(found_name, expected_name) for expected_name in expected_names):
            assert False, f"Unexpected person found: {found_name}"

    for name, expected_person in expected_dict.items():
        # Find the matching found_person using same_name
        found_person = None
        for found_name, candidate in found_dict.items():
            if same_name(name, found_name):
                found_person = candidate
                break
        assert found_person is not None, f"Expected person not found for comparison: {name}"
        for field in expected_person.model_fields:
            if field in ignore_fields or field == "name":
                continue
            expected_val = getattr(expected_person, field)
            found_val = getattr(found_person, field)
            # For lists: pass if at least one expected item is present in found (case-insensitive for strings)
            if isinstance(expected_val, list):
                expected_norm = set(normalize(expected_val))
                found_norm = set(normalize(found_val))
                if expected_norm:
                    assert any(item in found_norm for item in expected_norm), (
                        f"Mismatch in list field '{field}' for person: {name} "
                        f"(expected at least one of: {expected_norm}, found: {found_norm})"
                    )
            else:
                expected_norm = normalize(expected_val)
                found_norm = normalize(found_val)
                assert expected_norm == found_norm, (
                    f"Mismatch in field '{field}' for person: {name} "
                    f"(expected: {expected_norm}, found: {found_norm})"
                )