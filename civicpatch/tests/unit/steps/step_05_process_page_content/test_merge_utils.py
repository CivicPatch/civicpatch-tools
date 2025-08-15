import pytest
from steps.step_05_process_page_content.merge_utils import normalize_name, find_canonical_name, update_name_map, append_to_people_by_name, group_people_by_name
from schemas import LLMPerson, PeopleByName, OtherNamesByCanonicalName, LLMDataPoint


def test_normalize_name():
    assert normalize_name("John Doe") == "John Doe"
    assert normalize_name("Doe, John") == "John Doe"
    assert normalize_name("  Jane Smith  ") == "Jane Smith"
    assert normalize_name("Dr. John A. Doe") == "John Doe"


def test_find_canonical_name():
    people_by_name = {
        "John Doe": [],
        "Jane Smith": []
    }
    assert find_canonical_name("John Doe", people_by_name) == "John Doe"
    assert find_canonical_name("Jane Smith", people_by_name) == "Jane Smith"
    assert find_canonical_name("Johnny Doe", people_by_name) == "John Doe"


def test_update_name_map():
    name_map = {
        "John Doe": ["J. Doe"]
    }
    updated_map = update_name_map(name_map, "John Doe", "Johnny")
    assert updated_map == {
        "John Doe": ["J. Doe", "Johnny"]
    }

    updated_map = update_name_map(name_map, "Jane Smith", "J. Smith")
    assert updated_map == {
        "John Doe": ["J. Doe"],
        "Jane Smith": ["J. Smith"]
    }


def test_append_to_people_by_name():
    people_by_name = {
        "John Doe": [LLMPerson(name="John Doe", roles=[], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None)]
    }
    new_people = [
        LLMPerson(name="Johnny Doe", roles=[], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None)
    ]
  
    updated_people_by_name = append_to_people_by_name(people_by_name, "John Doe", new_people)
    assert len(updated_people_by_name["John Doe"]) == 2

    updated_people_by_name = append_to_people_by_name(people_by_name, "Jane Smith", new_people)
    assert "Jane Smith" in updated_people_by_name
    assert len(updated_people_by_name["Jane Smith"]) == 1


def test_group_people_by_name():
    names = {
        "John Doe": ["J. Doe", "Johnny"],
        "Jane Smith": ["J. Smith"]
    }
    people_by_name = {
        "John Doe": [
            LLMPerson(
                name="John Doe",
                roles=[],
                divisions=[],
                phone_number=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
                email=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
                website=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
                start_date=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
                end_date=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason="")
            )
        ],
        "Jane Smith": []
    }
    people_to_link = [
        LLMPerson(
            name="Johnny Doe",
            roles=[],
            divisions=[],
            phone_number=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            email=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            website=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            start_date=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            end_date=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason="")
        ),
        LLMPerson(
            name="Jane Smith",
            roles=[],
            divisions=[],
            phone_number=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            email=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            website=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            start_date=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason=""),
            end_date=LLMDataPoint(data=None, llm_confidence=0.0, llm_confidence_reason="")
        )
    ]

    name_map, updated_people_by_name = group_people_by_name(names, people_by_name, people_to_link)

    # Ensure aliases are deduplicated and sorted
    assert name_map == {
        "John Doe": ["J. Doe", "John Doe", "Johnny", "Johnny Doe"],
        "Jane Smith": ["J. Smith", "Jane Smith"]
    }
    assert len(updated_people_by_name["John Doe"]) == 2
    assert len(updated_people_by_name["Jane Smith"]) == 1