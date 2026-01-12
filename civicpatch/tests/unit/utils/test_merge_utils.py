import pytest
from utils.merge_utils import (
  normalize_name, 
  update_name_map, 
  append_to_people_by_name,
  group_people_by_name

)
from jobs.people_collector.schemas import LLMPerson

pytestmark = pytest.mark.unit

def test_normalize_name():
    assert normalize_name("John Doe") == "John Doe"
    assert normalize_name("  Jane Smith  ") == "Jane Smith"

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
        "John Doe": [LLMPerson(name="John Doe", roles=[], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    new_people = [
        LLMPerson(name="Johnny Doe", roles=[], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
  
    updated_people_by_name = append_to_people_by_name(people_by_name, "John Doe", new_people)
    assert len(updated_people_by_name["John Doe"]) == 2

    updated_people_by_name = append_to_people_by_name(people_by_name, "Jane Smith", new_people)
    assert "Jane Smith" in updated_people_by_name
    assert len(updated_people_by_name["Jane Smith"]) == 1

    assert len(updated_people_by_name["John Doe"]) == 2
    assert len(updated_people_by_name["Jane Smith"]) == 1

def test_group_people_by_name_basic():
    """Test basic grouping of people with no existing mappings"""
    known_mappings = {}
    people_by_name = {}
    people_to_link = [
        LLMPerson(name="John Doe", roles=["Mayor"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Jane Smith", roles=["Council"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert "John Doe" in updated_mappings
    assert "Jane Smith" in updated_mappings
    assert updated_mappings["John Doe"] == ["John Doe"]
    assert updated_mappings["Jane Smith"] == ["Jane Smith"]
    assert len(updated_people["John Doe"]) == 1
    assert len(updated_people["Jane Smith"]) == 1


def test_group_people_by_name_with_known_mappings():
    """Test grouping with existing known mappings"""
    known_mappings = {
        "John Doe": ["J. Doe", "Johnny"]
    }
    people_by_name = {}
    people_to_link = [
        LLMPerson(name="J. Doe", roles=["Mayor"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Johnny", roles=["Council"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert "John Doe" in updated_mappings
    assert "J. Doe" in updated_mappings["John Doe"]
    assert "Johnny" in updated_mappings["John Doe"]
    assert len(updated_people["John Doe"]) == 2


def test_group_people_by_name_with_existing_people():
    """Test grouping with existing people_by_name"""
    known_mappings = {}
    people_by_name = {
        "John Doe": [LLMPerson(name="John Doe", roles=["Existing"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    people_to_link = [
        LLMPerson(name="John Doe", roles=["Mayor"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert len(updated_people["John Doe"]) == 2
    assert updated_mappings["John Doe"] == ["John Doe"]


def test_group_people_by_name_similarity_matching():
    """Test grouping with name similarity matching"""
    known_mappings = {}
    people_by_name = {
        "John Doe": [LLMPerson(name="John Doe", roles=["Existing"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    people_to_link = [
        LLMPerson(name="Jon Doe", roles=["Mayor"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert len(updated_people["John Doe"]) == 2
    assert "Jon Doe" in updated_mappings["John Doe"]


def test_group_people_by_name_preserves_known_mappings():
    """Test that known mappings are preserved in output"""
    known_mappings = {
        "John Doe": ["J. Doe", "Johnny"],
        "Jane Smith": ["J. Smith"]
    }
    people_by_name = {}
    people_to_link = []
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert "John Doe" in updated_mappings
    assert "Jane Smith" in updated_mappings
    assert "J. Doe" in updated_mappings["John Doe"]
    assert "Johnny" in updated_mappings["John Doe"]
    assert "J. Smith" in updated_mappings["Jane Smith"]


def test_group_people_by_name_deduplication():
    """Test that duplicate names are deduplicated and sorted"""
    known_mappings = {
        "John Doe": ["Johnny"]
    }
    people_by_name = {}
    people_to_link = [
        LLMPerson(name="John Doe", roles=["Mayor"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Johnny", roles=["Council"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="John Doe", roles=["Deputy"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    # Check deduplication
    john_doe_aliases = updated_mappings["John Doe"]
    assert john_doe_aliases.count("John Doe") == 1
    assert john_doe_aliases.count("Johnny") == 1
    # Check sorting
    assert john_doe_aliases == sorted(john_doe_aliases)


def test_group_people_by_name_empty_inputs():
    """Test with empty inputs"""
    known_mappings = {}
    people_by_name = {}
    people_to_link = []
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert updated_mappings == {}
    assert updated_people == {}


def test_group_people_by_name_complex_scenario():
    """Test complex scenario with multiple name variations and mappings"""
    known_mappings = {
        "John Smith": ["J. Smith"]
    }
    people_by_name = {
        "Jane Doe": [LLMPerson(name="Jane Doe", roles=["Existing"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    people_to_link = [
        LLMPerson(name="John Smith", roles=["Mayor"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="J. Smith", roles=["Council"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Jane Doe", roles=["Deputy"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Bob Johnson", roles=["Clerk"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    # Check John Smith grouping
    assert "John Smith" in updated_mappings
    assert set(updated_mappings["John Smith"]) == {"John Smith", "J. Smith"}
    assert len(updated_people["John Smith"]) == 2
    
    # Check Jane Doe grouping
    assert "Jane Doe" in updated_mappings
    assert updated_mappings["Jane Doe"] == ["Jane Doe"]
    assert len(updated_people["Jane Doe"]) == 2
    
    # Check Bob Johnson
    assert "Bob Johnson" in updated_mappings
    assert updated_mappings["Bob Johnson"] == ["Bob Johnson"]
    assert len(updated_people["Bob Johnson"]) == 1


def test_group_people_by_name_whitespace_handling():
    """Test that whitespace in names is properly handled"""
    known_mappings = {}
    people_by_name = {}
    people_to_link = [
        LLMPerson(name="  John Doe  ", roles=["Mayor"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="John Doe", roles=["Council"], divisions=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_mappings, updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    # Should be grouped under the same canonical name
    assert len(updated_mappings) == 1
    canonical_name = list(updated_mappings.keys())[0]
    assert len(updated_people[canonical_name]) == 2
    assert "John Doe" in updated_mappings[canonical_name]
    assert "John Doe" in updated_mappings[canonical_name]