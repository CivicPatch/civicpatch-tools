import pytest
import time
import os
import json
import utils.llm_utils as llm_utils
from services.together_ai.llm import run_prompt
from services.together_ai.prompts import municipality_officials_prompt
from schemas import PeopleArrayLLMResponseSchema

def test_run_prompt_integration():
    """Integration test for run_prompt using actual environment variables and API."""

    # Ensure the environment variable is set
    api_key = os.getenv("TOGETHER_AI_TOKEN")
    assert api_key, "TOGETHER_AI_TOKEN must be set in environment variables for integration testing."

    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:wa/place:spokane"

    # Load content from the fixture file
    current_dir = os.path.dirname(__file__)  # Get the directory of the current file
    fixture_path = os.path.join(current_dir, "../fixtures/spokane_with_people.md")
    with open(fixture_path, "r") as file:
        content = file.read()

    # Load expected result from the fixture file
    expected_path = os.path.join(current_dir, "../fixtures/spokane_with_people_expected.json")
    with open(expected_path, "r") as file:
        expected_result = json.load(file)

    people_hint = [
                {
                    "name": "Lisa Brown",
                    "roles": [
                        "Mayor"
                    ]
                },
                {
                    "name": "Betsy Wilkerson",
                    "roles": [
                        "City Council President"
                    ]
                },
                {
                    "name": "Jonathan Bingle",
                    "roles": [
                        "City Council Member"
                    ]
                },
                {
                    "name": "Michael Cathcart",
                    "roles": [
                        "City Council Member"
                    ]
                },
                {
                    "name": "Paul Dillon",
                    "roles": [
                        "City Council Member"
                    ]
                },
                {
                    "name": "Shelby Lambdin",
                    "roles": [
                        "City Council Member"
                    ]
                },
                {
                    "name": "Zack Zappone",
                    "roles": [
                        "City Council Member"
                    ]
                },
                {
                    "name": "Kitty Klitzke",
                    "roles": [
                        "City Council Member"
                    ]
                }
            ] 


    prompt = municipality_officials_prompt(
        government_type="mayor_council",
        people_hint=people_hint # Adjust if you want to provide hints
    )

    start_time = time.time()

    result = run_prompt(jurisdiction_ocdid, prompt, content=content, response_schema=PeopleArrayLLMResponseSchema)
    result = result.model_dump() 

    end_time = time.time()

    assert end_time - start_time < 60, "Prompt execution took too long."

    #print(json.dumps(result, indent=4))
    print("Finished in {:.2f} seconds".format(end_time - start_time))
    
    # Sort both lists by name
    actual_people = sorted(result["people"], key=lambda x: x["name"])
    expected_people = sorted(expected_result["people"], key=lambda x: x["name"])

    # First check for missing or extra people
    actual_names = {p["name"] for p in actual_people}
    expected_names = {p["name"] for p in expected_people}
    missing_names = expected_names - actual_names
    extra_names = actual_names - expected_names

    if missing_names or extra_names:
        error_message = []
        if missing_names:
            error_message.append("\nMissing people:")
            for name in sorted(missing_names):
                error_message.append(f"  - {name}")
                # Find and print their expected roles
                expected_roles = next(p["roles"] for p in expected_people if p["name"] == name)
                error_message.append(f"    Expected roles: {expected_roles}")
        
        if extra_names:
            error_message.append("\nExtra people found:")
            for name in sorted(extra_names):
                error_message.append(f"  - {name}")
                # Find and print their actual roles
                actual_roles = next(p["roles"] for p in actual_people if p["name"] == name)
                error_message.append(f"    Actual roles: {actual_roles}")
        
        raise AssertionError("\n".join(error_message))

    # Now check the length
    assert len(actual_people) == len(expected_people), \
        f"Number of people mismatch. Got {len(actual_people)}, expected {len(expected_people)}"

    # Assert we have the same set of names
    actual_names = {p["name"] for p in actual_people}
    expected_names = {p["name"] for p in expected_people}
    missing_names = expected_names - actual_names
    extra_names = actual_names - expected_names
    
    assert not missing_names and not extra_names, \
        f"Name mismatches:\nMissing: {missing_names}\nExtra: {extra_names}"

    # Compare sorted lists
    for actual_person, expected_person in zip(actual_people, expected_people):
        print(f"Comparing person: {actual_person['name']}")
        assert actual_person["name"] == expected_person["name"], \
            f"Name mismatch: {actual_person['name']} != {expected_person['name']}"
        
        assert_roles(actual_person["roles"], expected_person["roles"])
        
        maybe_assert_divisions(actual_person["divisions"], expected_person["divisions"])
        
        # Compare single value fields directly
        assert actual_person["image"] == expected_person["image"], \
            f"Image mismatch: {actual_person['image']} != {expected_person['image']}"
        assert actual_person["phone_number"] == expected_person["phone_number"], \
            f"Phone number mismatch: {actual_person['phone_number']} != {expected_person['phone_number']}"
        assert actual_person["email"] == expected_person["email"], \
            f"Email mismatch: {actual_person['email']} != {expected_person['email']}"

    print("All assertions passed!")

def assert_roles(action_roles, expected_roles):
    """
    Helper function to assert that roles match either through:
    1. Set intersection (exact matches)
    2. Substring matches (e.g. "Council Member" matches "City Council Member")
    """
    actual_set = set(action_roles)
    expected_set = set(expected_roles)

    # Check for exact matches first
    if actual_set & expected_set:
        return

    # If no exact matches, check for substring matches
    for expected_role in expected_roles:
        for actual_role in action_roles:
            if expected_role.lower() in actual_role.lower():
                return
            if actual_role.lower() in expected_role.lower():
                return

    # If we get here, no matches were found
    raise AssertionError(
        f"No matching roles found (tried exact and substring matches).\n"
        f"Expected roles: {expected_set}\n"
        f"Actual roles: {actual_set}"
    )

def maybe_assert_divisions(actual_divisions, expected_divisions):
    """
    Helper function to assert that actual divisions match expected divisions.
    """
    actual_set = set(actual_divisions)
    expected_set = set(expected_divisions)

    # Only run assertion if either sets contain "district" or "ward"
    # This is hardcoded because divisions are pretty important
    if "district" in actual_set or "ward" in actual_set or "district" in expected_set or "ward" in expected_set:
        assert actual_set == expected_set, f"Divisions mismatch: {actual_set} != {expected_set}"