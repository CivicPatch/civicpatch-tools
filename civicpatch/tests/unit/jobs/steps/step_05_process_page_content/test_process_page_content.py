import pytest
import os
from unittest.mock import patch
from jobs.people_collector.schemas import (
    LLMPerson, LinkStatus, WorkflowStatus, ProcessPageContentStep, Link
)
from jobs.people_collector.steps.step_05_process_page_content.process_page_content import has_role_and_contact_info, move_links_to_top
from utils.url_utils import format_url_to_folder

pytestmark = pytest.mark.unit

def test_has_role_and_contact_info_with_valid_contact_info_and_role():
    """Test when there are at least two different types of contact info and a matching role."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email="john@example.com", url=None, divisions=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["council"], phone=None, email=None, url="http://example.com", divisions=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == True

def test_has_role_and_contact_info_with_insufficient_contact_info():
    """Test when there is only one type of contact info across all records."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email=None, url=None, divisions=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["council"], phone=None, email=None, url=None, divisions=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_no_matching_role():
    """Test when there is no matching role."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["teacher"], phone="123-456-7890", email="john@example.com", url=None, divisions=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["engineer"], phone=None, email=None, url="http://example.com", divisions=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_multiple_contact_info_same_type():
    """Test when there are multiple records with the same type of contact info."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email=None, url=None, divisions=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone="987-654-3210", email=None, url=None, divisions=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_exactly_three_contact_info_types():
    """Test when there are exactly two different types of contact info."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email=None, url="https://example.com", divisions=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone=None, email="jane@example.com", url=None, divisions=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == True

def test_has_role_and_contact_info_with_no_contact_info():
    """Test when there is no contact info."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone=None, email=None, url=None, divisions=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone=None, email=None, url=None, divisions=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_no_records():
    """Test when there are no records."""
    roles = ["mayor", "council"]
    records = []
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_three_contact_info_types():
    """Test when there are three different types of contact info."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email="john@example.com", url=None, divisions=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone=None, email=None, url="http://example.com", divisions=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == True

def test_move_existing_link_to_top():
    domain = "https://foo.com"
    links = [
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name="", is_profile_page=False),
        Link(url="https://foo.com/b", status=LinkStatus.DONE.value, folder_name="", is_profile_page=False),
        Link(url="https://foo.com/c", status=LinkStatus.PENDING.value, folder_name="", is_profile_page=False),
    ]
    result = move_links_to_top(domain, ["https://foo.com/b"], links)
    urls = [l.url for l in result]
    assert urls == ["https://foo.com/a", "https://foo.com/c", "https://foo.com/b"]

def test_add_new_link():
    domain = "https://foo.com"
    links = [
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name="", is_profile_page=False),
        Link(url="https://foo.com/b", status=LinkStatus.DONE.value, folder_name="", is_profile_page=False),
    ]
    # Add new link 'c'
    result = move_links_to_top(domain, ["https://foo.com/c"], links)
    urls = [l.url for l in result]
    # Should be: a (PENDING), c (PENDING), b (DONE)
    assert urls == ["https://foo.com/a", "https://foo.com/c", "https://foo.com/b"]
    assert result[1].status == LinkStatus.PENDING.value

def test_ignore_out_of_domain():
    domain = "https://foo.com"
    links = [
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name="", is_profile_page=False),
    ]
    # Try to add out-of-domain link
    result = move_links_to_top(domain, ["https://bar.com/x"], links)
    urls = [l.url for l in result]
    assert urls == ["https://foo.com/a"]

def test_multiple_links():
    domain = "https://foo.com"
    links = [
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name="", is_profile_page=False),
        Link(url="https://foo.com/b", status=LinkStatus.DONE.value, folder_name="", is_profile_page=False),
    ]
    # Add new and move existing
    result = move_links_to_top(domain, ["https://foo.com/b", "https://foo.com/c"], links)
    urls = [l.url for l in result]
    # Should be: a (PENDING), c (PENDING), b (DONE)
    assert urls == ["https://foo.com/a", "https://foo.com/c", "https://foo.com/b"]