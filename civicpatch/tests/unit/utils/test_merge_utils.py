import pytest
from utils.merge_utils import (
  normalize_name, 
  append_to_people_by_name,
  group_people_by_name,
  to_field_set_from_record,
  is_weakly_tied,
)
from jobs.people_collector.schemas import LLMPerson
from domain.models import Person

pytestmark = pytest.mark.unit

def test_normalize_name():
    assert normalize_name("John Doe") == "John Doe"
    assert normalize_name("  Jane Smith  ") == "Jane Smith"

def test_append_to_people_by_name():
    people_by_name = {
        "John Doe": [LLMPerson(name="John Doe", roles=[], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    new_people = [
        LLMPerson(name="Johnny Doe", roles=[], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
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
        LLMPerson(name="John Doe", roles=["Mayor"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Jane Smith", roles=["Council"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    assert "John Doe" in updated_people
    assert "Jane Smith" in updated_people

def test_group_people_by_name_with_known_mappings():
    """Test grouping with existing known mappings."""
    known_mappings = {
        "John Doe": ["J. Doe", "Johnny"]
    }
    people_by_name = {}
    people_to_link = [
        LLMPerson(name="J. Doe", roles=["Mayor"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Johnny", roles=["Council"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert len(updated_people["John Doe"]) == 2


def test_group_people_by_name_with_existing_people():
    """Test grouping with existing people_by_name"""
    known_mappings = {}
    people_by_name = {
        "John Doe": [LLMPerson(name="John Doe", roles=["Existing"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    people_to_link = [
        LLMPerson(name="John Doe", roles=["Mayor"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert len(updated_people["John Doe"]) == 2


def test_group_people_by_name_similarity_matching():
    """Test grouping with name similarity matching"""
    known_mappings = {}
    people_by_name = {
        "John Doe": [LLMPerson(name="John Doe", roles=["Existing"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    people_to_link = [
        LLMPerson(name="Jon Doe", roles=["Mayor"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)

    # OK to have them separate -- this is used just for process_page_content
    assert len(updated_people.keys()) == 2
    assert "John Doe" in updated_people
    assert "Jon Doe" in updated_people


def test_group_people_by_name_deduplication():
    """Test that duplicate names are deduplicated and sorted."""
    known_mappings = {
        "John Doe": ["Johnny"]
    }
    people_by_name = {}
    people_to_link = [
        LLMPerson(name="John Doe", roles=["Mayor"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Johnny", roles=["Council"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="John Doe", roles=["Deputy"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    assert len(updated_people["John Doe"]) == 3
    

def test_group_people_by_name_empty_inputs():
    """Test with empty inputs"""
    known_mappings = {}
    people_by_name = {}
    people_to_link = []
    
    updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    assert updated_people == {}


def test_group_people_by_name_complex_scenario():
    """Test complex scenario with multiple name variations and mappings"""
    known_mappings = {
        "John Smith": ["J. Smith"]
    }
    people_by_name = {
        "Jane Doe": [LLMPerson(name="Jane Doe", roles=["Existing"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")]
    }
    people_to_link = [
        LLMPerson(name="John Smith", roles=["Mayor"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="J. Smith", roles=["Council"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Jane Doe", roles=["Deputy"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test"),
        LLMPerson(name="Bob Johnson", roles=["Clerk"], designations=[], phone_number=None, email=None, website=None, start_date=None, end_date=None, source_url="test")
    ]
    
    updated_people = group_people_by_name(known_mappings, people_by_name, people_to_link)
    
    # Check John Smith grouping
    assert len(updated_people["John Smith"]) == 2
    
    # Check Jane Doe grouping
    assert len(updated_people["Jane Doe"]) == 2
    
    # Check Bob Johnson
    assert len(updated_people["Bob Johnson"]) == 1


def test_to_field_set_from_record():
    class Dummy:
        pass

    # Only 'email' as string
    r1 = Dummy()
    r1.email = "a@example.com"
    assert to_field_set_from_record(r1, ["email"]) == {"a@example.com"}

    # Only 'emails' as string
    r2 = Dummy()
    r2.emails = "b@example.com"
    assert to_field_set_from_record(r2, ["emails"]) == {"b@example.com"}

    # Only 'emails' as list
    r3 = Dummy()
    r3.emails = ["c@example.com", "d@example.com"]
    assert to_field_set_from_record(r3, ["emails"]) == {"c@example.com", "d@example.com"}

    # Both 'email' and 'emails'
    r4 = Dummy()
    r4.email = "e@example.com"
    r4.emails = ["f@example.com"]
    assert to_field_set_from_record(r4, ["email", "emails"]) == {"e@example.com", "f@example.com"}

    # Neither present
    r5 = Dummy()
    assert to_field_set_from_record(r5, ["email", "emails"]) == set()

def test_to_field_set_from_record_urls():
    class Dummy:
        pass

    # Only 'url' as string
    r1 = Dummy()
    r1.url = "http://example.com"
    assert to_field_set_from_record(r1, ["url"]) == {"http://example.com"}

    # Only 'urls' as string
    r2 = Dummy()
    r2.urls = "http://example.org"
    assert to_field_set_from_record(r2, ["urls"]) == {"http://example.org"}

    # Only 'urls' as list
    r3 = Dummy()
    r3.urls = ["http://example.net", "http://example.edu"]
    assert to_field_set_from_record(r3, ["urls"]) == {"http://example.net", "http://example.edu"}

    # Both 'url' and 'urls'
    r4 = Dummy()
    r4.url = "http://example.gov"
    r4.urls = ["http://example.info"]
    assert to_field_set_from_record(r4, ["url", "urls"]) == {"http://example.gov", "http://example.info"}

    # Neither present
    r5 = Dummy()
    assert to_field_set_from_record(r5, ["url", "urls"]) == set()

def test_is_weakly_tied_llm_person():
    class Dummy:
        pass
    person1 = Dummy()
    person1.name = "John Doe"
    person1.roles = ["Mayor"]
    person1.email = ["john@example.com"]

    person2 = Dummy()
    person2.name = "Johnathan Doe"
    person2.roles = ["Mayor"]
    person2.email = ["john@example.com"]

    assert is_weakly_tied({}, person1, person2) == True

def test_is_weakly_tied_person():
    class Dummy:
        pass

    person1 = Dummy()
    person1.name = "Jane Smith"
    person1.roles = ["Council"]
    person1.emails = ["jane@example.com"]

    person2 = Dummy()
    person2.name = "Janet Smith"
    person2.roles = ["Council"]
    person2.emails = ["jane@example.com"]
    assert is_weakly_tied({}, person1, person2) == True

def test_is_not_weakly_tied_different_roles_and_emails():
    class Dummy:
        pass
    person1 = Dummy()
    person1.name = "Alice Johnson"
    person1.roles = ["Mayor"]
    person1.emails = ["alice@example.com"]

    person2 = Dummy()
    person2.name = "Bob Johnson"
    person2.roles = ["Council"]
    person2.emails = ["bob@example.com"]
    assert is_weakly_tied({}, person1, person2) == False

def test_is_weakly_tied_same_identity():
    """Test is_weakly_tied when both records have the same identity."""
    identity_names = {"John Doe": ["John Doe", "Johnny", "J. Doe"]}
    record1 = LLMPerson(name="Johnny", roles=[], email=None, url=None, designations=[], source_url="test")
    record2 = LLMPerson(name="J. Doe", roles=[], email=None, url=None, designations=[], source_url="test")
    assert is_weakly_tied(identity_names, record1, record2) == True

def test_is_weakly_tied_different_identity():
    """Test is_weakly_tied when both records have different identities."""
    identity_names = {
        "John Doe": ["Johnny"],
        "Jane Smith": ["J. Smith"]
    }
    record1 = LLMPerson(name="Johnny", roles=[], email=None, url=None, designations=[], source_url="test")
    record2 = LLMPerson(name="J. Smith", roles=[], email=None, url=None, designations=[], source_url="test")
    assert is_weakly_tied(identity_names, record1, record2) == False

def test_is_weakly_tied_name_overlap():
    """Test is_weakly_tied when names overlap."""
    identity_names = {}
    record1 = LLMPerson(name="John Doe", roles=[], email=None, url=None, designations=[], source_url="test")
    record2 = LLMPerson(name="Jon Doe", roles=[], email=None, url=None, designations=[], source_url="test")
    assert is_weakly_tied(identity_names, record1, record2) == False

def test_is_weakly_tied_matching_roles():
    """Test is_weakly_tied when roles match."""
    identity_names = {}
    record1 = LLMPerson(name="John Doe", roles=["Mayor"], email=None, url=None, designations=[], source_url="test")
    record2 = LLMPerson(name="Jon Doe", roles=["Mayor"], email=None, url=None, designations=[], source_url="test")
    assert is_weakly_tied(identity_names, record1, record2) == True

def test_is_weakly_tied_email_overlap():
    """Test is_weakly_tied when emails overlap."""
    identity_names = {}
    record1 = LLMPerson(name="John Doe", roles=[], email="john@example.com", url=None, designations=[], source_url="test")
    record2 = LLMPerson(name="Jon Doe", roles=[], email="john@example.com", url=None, designations=[], source_url="test")
    assert is_weakly_tied(identity_names, record1, record2) == True

def test_is_weakly_tied_url_overlap():
    """Test is_weakly_tied when URLs overlap."""
    identity_names = {}
    record1 = LLMPerson(name="Abigail Doe", roles=[], email=None, url="http://example.com", designations=[], source_url="test")
    record2 = LLMPerson(name="Abby Doe", roles=[], email=None, url="http://example.com", designations=[], source_url="test")
    assert is_weakly_tied({}, record1, record2) == False

def test_is_weakly_tied_no_overlap():
    """Test is_weakly_tied when there is no overlap."""
    identity_names = {}
    record1 = LLMPerson(name="John Doe", roles=["Mayor"], email=None, url="http://example.com", designations=[], source_url="test")
    record2 = LLMPerson(name="Jane Smith", roles=["Council"], email=None, url="http://example.org", designations=[], source_url="test")
    assert is_weakly_tied(identity_names, record1, record2) == False

import pytest
from utils.merge_utils import find_indexed_name, PeopleByName, OtherNamesByCanonicalName

def test_find_indexed_name_with_known_mapping():
    """Test when the name is found in known mappings."""
    known_mappings = {
        "John Smith": ["Jon Smith", "Jonathan Smith"],
        "Jane Doe": ["Janet Doe"]
    }
    people_by_name = {}

    assert find_indexed_name("Jon Smith", people_by_name, known_mappings) == "John Smith"
    assert find_indexed_name("Janet Doe", people_by_name, known_mappings) == "Jane Doe"
    assert find_indexed_name("Unknown Name", people_by_name, known_mappings) == "Unknown Name"

def test_find_indexed_name_with_similarity_matching():
    """Test when the name is matched based on similarity."""
    known_mappings = {}
    people_by_name = {
        "John Smith": [],
        "Jane Doe": [],
        "Alice Johnson": []
    }

    assert find_indexed_name("Jon Smith", people_by_name, known_mappings) == "John Smith"
    assert find_indexed_name("Janey Doe", people_by_name, known_mappings) == "Jane Doe"
    assert find_indexed_name("Alicia Johnson", people_by_name, known_mappings) == "Alice Johnson"

def test_find_indexed_name_with_last_name_containment():
    """Test when the last name contains or is contained by another."""
    known_mappings = {}
    people_by_name = {
        "John Smith": [],
        "Jane Doe": [],
        "Alice Johnson": []
    }

    assert find_indexed_name("John Smithson", people_by_name, known_mappings) == "John Smith"
    assert find_indexed_name("Jane y. Doe", people_by_name, known_mappings) == "Jane Doe"

def test_find_indexed_name_no_match():
    """Test when no match is found."""
    known_mappings = {}
    people_by_name = {
        "John Smith": [],
        "Jane Doe": [],
        "Alice Johnson": []
    }

    assert find_indexed_name("Unknown Name", people_by_name, known_mappings) == "Unknown Name"

def test_find_indexed_name_with_empty_people_by_name():
    """Test when people_by_name is empty."""
    known_mappings = {}
    people_by_name = {}

    assert find_indexed_name("John Smith", people_by_name, known_mappings) == "John Smith"

def test_find_indexed_name_with_empty_known_mappings():
    """Test when known_mappings is empty."""
    known_mappings = {}
    people_by_name = {
        "John Smith": [],
        "Jane Doe": [],
        "Alice Johnson": []
    }

    assert find_indexed_name("John Smith", people_by_name, known_mappings) == "John Smith"
    assert find_indexed_name("Unknown Name", people_by_name, known_mappings) == "Unknown Name"
