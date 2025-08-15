import pytest
import time
import os
import json
from services.together_ai.llm import run_prompt
from services.together_ai.prompts import municipality_officials_prompt
from utils.data_utils import MunicipalityContext
from schemas import PeopleArrayLLMResponseSchema

def test_run_prompt_integration():
    """Integration test for run_prompt using actual environment variables and API."""

    # Ensure the environment variable is set
    api_key = os.getenv("TOGETHER_AI_TOKEN")
    assert api_key, "TOGETHER_AI_TOKEN must be set in environment variables for integration testing."

    # Load content from the fixture file
    current_dir = os.path.dirname(__file__)  # Get the directory of the current file
    fixture_path = os.path.join(current_dir, "../fixtures/spokane_with_people.md")
    with open(fixture_path, "r") as file:
        content = file.read()

    # Load expected result from the fixture file
    expected_path = os.path.join(current_dir, "../fixtures/spokane_with_people_expected.json")
    with open(expected_path, "r") as file:
        expected_result = json.load(file)

    municipality_context: MunicipalityContext = {
        "state": "wa",
        "municipality_entry": {
            "name": "Spokane",
        }
    }

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
        content=content,
        people_hint=people_hint # Adjust if you want to provide hints
    )

    start_time = time.time()

    result = run_prompt(municipality_context, prompt, response_schema=PeopleArrayLLMResponseSchema)
    end_time = time.time()

    assert end_time - start_time < 60, "Prompt execution took too long."

    print("Result:")
    print(json.dumps(result, indent=4))
    print("Finished in {:.2f} seconds".format(end_time - start_time))
    
    missing_people = [
        expected_person["name"]
        for expected_person in expected_result["people"]
        if not any(
            actual_person["name"] == expected_person["name"]
            for actual_person in result["people"]
        )
    ]
    assert not missing_people, f"Missing people in the result: {len(missing_people)} - {missing_people}"

    for actual_person, expected_person in zip(result["people"], expected_result["people"]):
        print(f"Comparing person: {actual_person['name']}")  # Debug statement for each person
        assert actual_person["name"] == expected_person["name"], f"Name mismatch: {actual_person['name']} != {expected_person['name']}"
        for actual_role, expected_role in zip(actual_person["roles"], expected_person["roles"]):
            print(f"Role comparison: {actual_role['data']} vs {expected_role['data']}")  # Debug statement for roles
            assert actual_role["data"] == expected_role["data"], f"Role mismatch: {actual_role['data']} != {expected_role['data']}"
        for actual_division, expected_division in zip(actual_person["divisions"], expected_person["divisions"]):
            print(f"Division comparison: {actual_division['data']} vs {expected_division['data']}")  # Debug statement for divisions
            assert actual_division["data"] == expected_division["data"], f"Division mismatch: {actual_division['data']} != {expected_division['data']}"
        print(f"Phone number comparison: {actual_person['phone_number']['data']} vs {expected_person['phone_number']['data']}")  # Debug statement for phone number
        assert actual_person["phone_number"]["data"] == expected_person["phone_number"]["data"], f"Phone number mismatch: {actual_person['phone_number']['data']} != {expected_person['phone_number']['data']}"
        print(f"Email comparison: {actual_person['email']['data']} vs {expected_person['email']['data']}")  # Debug statement for email
        assert actual_person["email"]["data"] == expected_person["email"]["data"], f"Email mismatch: {actual_person['email']['data']} != {expected_person['email']['data']}"

    print("All assertions passed!")