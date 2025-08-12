import pytest
from schemas import LLMPerson, LLMDataPoint, ProcessedLLMPeople
from steps.step_05_process_page_content.process_page_content import (
    update_progress, has_role_and_contact_info
)

def make_llm_person(name, roles=None, phone=None, email=None, website=None):
    dp = lambda val: LLMDataPoint(data=val, llm_confidence=1.0, llm_confidence_reason="test")
    return LLMPerson(
        name=name,
        roles=[dp(r) for r in (roles or [])],
        divisions=[],
        phone_number=dp(phone) if phone else dp(None),
        email=dp(email) if email else dp(None),
        website=dp(website) if website else dp(None),
        start_date=dp(None),
        end_date=dp(None)
    )

def test_has_role_and_contact_info_true():
    # One record has contact, another has role
    records = [
        make_llm_person("Alice", roles=[], phone="123"),
        make_llm_person("Alice", roles=["council member"])
    ]
    assert has_role_and_contact_info(["council member"], records) is True

def test_has_role_and_contact_info_false():
    # No record has contact info
    records = [
        make_llm_person("Alice", roles=["council member"]),
        make_llm_person("Alice", roles=[])
    ]
    assert has_role_and_contact_info(["council member"], records) is False

def test_has_role_and_contact_info_both_in_one():
    # One record has both
    records = [
        make_llm_person("Alice", roles=["council member"], phone="123")
    ]
    assert has_role_and_contact_info(["council member"], records) is True

def test_has_role_and_contact_info_multiple_roles():
    # Should match any role in the list
    records = [
        make_llm_person("Alice", roles=["mayor"], phone="123"),
        make_llm_person("Alice", roles=["council member"])
    ]
    assert has_role_and_contact_info(["council member", "mayor"], records) is True

def test_has_role_and_contact_info_no_roles():
    # No roles in filter
    records = [
        make_llm_person("Alice", roles=[], phone="123")
    ]
    assert has_role_and_contact_info([], records) is False

def test_update_progress_basic():
    # Simulate processed data for two LLMs
    processed_data = {
        "google_gemini": {
            "alice": {
                "records": [
                    make_llm_person("Alice", roles=["council member"], phone="123")
                ]
            },
            "bob": {
                "records": [
                    make_llm_person("Bob", roles=[], phone=None)
                ]
            }
        },
        "openai": {
            "alice": {
                "records": [
                    make_llm_person("Alice", roles=["council member"], phone="123")
                ]
            }
        }
    }
    roles = ["council member"]
    progress = {"current_data": 0}
    updated = update_progress(progress.copy(), processed_data, roles)
    # Only "alice" in both LLMs passes the filter, so min_length should be 1
    assert updated["current_data"] == 1

def test_update_progress_none_found():
    processed_data = {
        "google_gemini": {
            "bob": {
                "records": [
                    make_llm_person("Bob", roles=[], phone=None)
                ]
            }
        }
    }
    roles = ["council member"]
    progress = {"current_data": 0}
    updated = update_progress(progress.copy(), processed_data, roles)
    assert updated["current_data"] == 0

def test_update_progress_multiple_people():
    processed_data = {
        "google_gemini": {
            "alice": {
                "records": [
                    make_llm_person("Alice", roles=["council member"], phone="123")
                ]
            },
            "bob": {
                "records": [
                    make_llm_person("Bob", roles=["council member"], phone="456")
                ]
            }
        },
        "openai": {
            "alice": {
                "records": [
                    make_llm_person("Alice", roles=["council member"], phone="123")
                ]
            },
            "bob": {
                "records": [
                    make_llm_person("Bob", roles=["council member"], phone="456")
                ]
            }
        }
    }
    roles = ["council member"]
    progress = {"current_data": 0}
    updated = update_progress(progress.copy(), processed_data, roles)
    # Both "alice" and "bob" in both LLMs pass the filter, so min_length should be 2
    assert updated["current_data"] == 2