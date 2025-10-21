import pytest
from utils.merge_utils import normalize_name, find_canonical_name, update_name_map, append_to_people_by_name
from schemas import LLMPerson

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

    assert len(updated_people_by_name["John Doe"]) == 2
    assert len(updated_people_by_name["Jane Smith"]) == 1