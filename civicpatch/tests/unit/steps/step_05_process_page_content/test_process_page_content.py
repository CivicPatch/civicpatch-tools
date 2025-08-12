import pytest
from schemas import LLMPerson, LLMDataPoint, ProcessedLLMPeople, pydantic_to_dict, dict_to_pydantic
from steps.step_05_process_page_content.process_page_content import update_data

def make_llm_person(name):
    dp = LLMDataPoint(data="test", llm_confidence=1.0, llm_confidence_reason="test")
    return LLMPerson(
        name=name,
        roles=[dp],
        divisions=[dp],
        phone_number=dp,
        email=dp,
        website=dp,
        start_date=dp,
        end_date=dp
    )

def test_update_data_basic():
    # Setup initial processed data (as dict)
    processed_data = {
        "google_gemini": {
            "alice smith": ProcessedLLMPeople(names=["Alice Smith"], records=[make_llm_person("Alice Smith")])
        }
    }
    # Convert to dict for input (simulate what your pipeline does)
    processed_data_dict = pydantic_to_dict(processed_data)

    # Setup current_responses (LLMResponsesDict)
    current_responses = {
        "google_gemini": [make_llm_person("Bob Jones")]
    }

    # Run update_data
    updated = update_data(dict_to_pydantic(processed_data_dict, ProcessedLLMPeople), current_responses)

    # Check output structure
    assert "google_gemini" in updated
    assert any("Bob Jones" in p["names"] for p in updated["google_gemini"].values())
    assert any("Alice Smith" in p["names"] for p in updated["google_gemini"].values())

def test_update_data_merges_people():
    processed_data = {
        "openai": {
            "bob jones": ProcessedLLMPeople(names=["Bob Jones"], records=[make_llm_person("Bob Jones")])
        }
    }
    processed_data_dict = pydantic_to_dict(processed_data)
    current_responses = {
        "openai": [make_llm_person("Bob Jones"), make_llm_person("Alice Smith")]
    }
    updated = update_data(dict_to_pydantic(processed_data_dict, ProcessedLLMPeople), current_responses)
    assert "openai" in updated
    assert any("Alice Smith" in p["names"] for p in updated["openai"].values())
    assert any("Bob Jones" in p["names"] for p in updated["openai"].values())