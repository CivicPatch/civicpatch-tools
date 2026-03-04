import pytest
import os
from unittest.mock import patch
from jobs.people_collector.schemas import (
    LLMPerson, LinkStatus, WorkflowStatus, ProcessPageContentStep, Link
)
from jobs.people_collector.steps.step_05_process_page_content.process_page_content import has_role_and_contact_info, move_links_to_top
from utils.url_utils import format_url_to_folder
from jobs.people_collector.steps.step_05_process_page_content.process_page_content import check_page_heuristics
from jobs.people_collector.schemas import LLMPerson

pytestmark = pytest.mark.unit

def dummy_logger():
    class DummyLogger:
        def warning(self, msg):
            print(f"WARNING: {msg}")
    return DummyLogger()

def test_has_role_and_contact_info_with_valid_contact_info_and_role():
    """Test when there are at least two different types of contact info and a matching role."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email="john@example.com", url=None, designations=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["council"], phone=None, email=None, url="http://example.com", designations=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == True

def test_has_role_and_contact_info_with_insufficient_contact_info():
    """Test when there is only one type of contact info across all records."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email=None, url=None, designations=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["council"], phone=None, email=None, url=None, designations=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_no_matching_role():
    """Test when there is no matching role."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["teacher"], phone="123-456-7890", email="john@example.com", url=None, designations=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["engineer"], phone=None, email=None, url="http://example.com", designations=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_multiple_contact_info_same_type():
    """Test when there are multiple records with the same type of contact info."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email=None, url=None, designations=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone="987-654-3210", email=None, url=None, designations=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == False

def test_has_role_and_contact_info_with_exactly_three_contact_info_types():
    """Test when there are exactly two different types of contact info."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email=None, url="https://example.com", designations=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone=None, email="jane@example.com", url=None, designations=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == True

def test_has_role_and_contact_info_with_no_contact_info():
    """Test when there is no contact info."""
    roles = ["mayor", "council"]
    records = [
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone=None, email=None, url=None, designations=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone=None, email=None, url=None, designations=[], source_url="test"),
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
        LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone="123-456-7890", email="john@example.com", url=None, designations=[], source_url="test"),
        LLMPerson(name="Jane Doe", other_names=[], roles=["mayor"], phone=None, email=None, url="http://example.com", designations=[], source_url="test"),
    ]
    assert has_role_and_contact_info(roles, records) == True

def test_move_existing_link_to_top():
    domain = "https://foo.com"
    links = [
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name=""),
        Link(url="https://foo.com/b", status=LinkStatus.DONE.value, folder_name=""),
        Link(url="https://foo.com/c", status=LinkStatus.PENDING.value, folder_name=""),
    ]
    result = move_links_to_top(domain, ["https://foo.com/b"], links)
    urls = [l.url for l in result]
    assert urls == ["https://foo.com/a", "https://foo.com/c", "https://foo.com/b"]

def test_add_new_link():
    domain = "https://foo.com"
    links = [
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name=""),
        Link(url="https://foo.com/b", status=LinkStatus.DONE.value, folder_name=""),
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
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name=""),
    ]
    # Try to add out-of-domain link
    result = move_links_to_top(domain, ["https://bar.com/x"], links)
    urls = [l.url for l in result]
    assert urls == ["https://foo.com/a"]

def test_multiple_links():
    domain = "https://foo.com"
    links = [
        Link(url="https://foo.com/a", status=LinkStatus.PENDING.value, folder_name=""),
        Link(url="https://foo.com/b", status=LinkStatus.DONE.value, folder_name=""),
    ]
    # Add new and move existing
    result = move_links_to_top(domain, ["https://foo.com/b", "https://foo.com/c"], links)
    urls = [l.url for l in result]
    # Should be: a (PENDING), c (PENDING), b (DONE)
    assert urls == ["https://foo.com/a", "https://foo.com/c", "https://foo.com/b"]

def test_check_page_heuristics_returns_true_with_empty_records():
    assert check_page_heuristics(dummy_logger(), "Some markdown content", []) is True

def test_check_page_heuristics_returns_true_with_nonempty_records():
    records = [
        LLMPerson(
            name="Laura Palmer",
            other_names=[],
            roles=["mayor"],
            phone="555-9999",
            email="laura@palmer.com",
            url="http://palmer.com/laura",
            designations=["Ward 8"],
            source_url="http://palmer.com"
        )
    ]
    input_text = "Laura Palmer the mayor is available at laura@palmer.com or 555-9999. See http://palmer.com/laura for more details."
    assert check_page_heuristics(dummy_logger(), input_text, records) is True

def test_check_page_heuristics_returns_false_if_input_text_empty():
    records = [
        LLMPerson(
            name="Laura Palmer",
            other_names=[],
            roles=["mayor"],
            phone="555-9999",
            email="laura@palmer.com",
            url="http://palmer.com/laura",
            designations=["Ward 8"],
            source_url="http://palmer.com"
        )
    ]
    input_text = ""
    assert check_page_heuristics(dummy_logger(), input_text, records) is False

def test_check_page_heuristics_returns_false_if_role_not_in_text():
    records = [
        LLMPerson(
            name="Sam NoRoleInText",
            other_names=[],
            roles=["mayor"],
            phone="555-1234",
            email="sam@nole.com",
            url="http://nole.com/sam",
            designations=["Ward 1"],
            source_url="http://nole.com"
        )
    ]
    input_text = "Contact Sam NoRoleInText at sam@nole.com or 555-1234. See http://nole.com/sam. Ward 1."
    # "mayor" is not in input_text
    assert check_page_heuristics(dummy_logger(), input_text, records) is False

def test_check_page_heuristics_returns_false_if_phone_not_in_text():
    records = [
        LLMPerson(
            name="Pat NoPhoneInText",
            other_names=[],
            roles=["council"],
            phone="555-0000",
            email="pat@nophone.com",
            url="http://nophone.com/pat",
            designations=["Ward 2"],
            source_url="http://nophone.com"
        )
    ]
    input_text = "Council member Pat NoPhoneInText can be reached at pat@nophone.com. See http://nophone.com/pat. Ward 2."
    # "555-0000" is not in input_text
    assert check_page_heuristics(dummy_logger(), input_text, records) is False

def test_check_page_heuristics_returns_false_if_email_not_in_text():
    records = [
        LLMPerson(
            name="Alex NoEmailInText",
            other_names=[],
            roles=["mayor"],
            phone="555-5678",
            email="alex@noemail.com",
            url="http://noemail.com/alex",
            designations=["Ward 3"],
            source_url="http://noemail.com"
        )
    ]
    input_text = "Mayor Alex NoEmailInText is available at 555-5678 or http://noemail.com/alex. Ward 3."
    # "alex@noemail.com" is not in input_text
    assert check_page_heuristics(dummy_logger(), input_text, records) is False

def test_check_page_heuristics_returns_false_if_url_not_in_text():
    records = [
        LLMPerson(
            name="Jamie NoUrlInText",
            other_names=[],
            roles=["council"],
            phone="555-8765",
            email="jamie@nourl.com",
            url="http://nourl.com/jamie",
            designations=["Ward 4"],
            source_url="http://nourl.com"
        )
    ]
    input_text = "Council member Jamie NoUrlInText can be reached at jamie@nourl.com or 555-8765. Ward 4."
    # "http://nourl.com/jamie" is not in input_text
    assert check_page_heuristics(dummy_logger(), input_text, records) is False
