import pytest
from unittest.mock import patch, AsyncMock
from jobs.people_collector.schemas import (
    LLMPerson, LinkStatus, Link, RelevantPageResponseSchema
)
from jobs.people_collector.steps.step_05_process_page_content.process_page_content import (
    has_role_and_contact_info, check_page_heuristics, check_page_relevance, add_relevant_urls, normalize_record
)
from jobs.people_collector.schemas import LLMPerson
from tests.factories.workflow_context import workflow_context_factory

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

def test_check_page_heuristics_returns_true_with_empty_records():
    assert check_page_heuristics(dummy_logger(), "dummy-link", "Some markdown content", []) is True

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
    assert check_page_heuristics(dummy_logger(), "dummy-link", input_text, records) is True

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
    assert check_page_heuristics(dummy_logger(), "dummy-link", input_text, records) is False

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
    assert check_page_heuristics(dummy_logger(), "dummy-link", input_text, records) is False

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
    assert check_page_heuristics(dummy_logger(), "dummy-link", input_text, records) is False

def test_check_page_heuristics_matches_name_with_curly_apostrophe_in_text():
    # LLM returns straight apostrophe; page has curly right-single-quote (U+2019)
    records = [
        LLMPerson(
            name="Mario D'Agostino",
            other_names=[],
            roles=["council"],
            phone=None,
            email=None,
            url=None,
            designations=[],
            source_url="http://example.com",
        )
    ]
    input_text = "Council member Mario D\u2019Agostino represents District 4."
    assert check_page_heuristics(dummy_logger(), "http://example.com", input_text, records) is True

def test_check_page_heuristics_matches_name_with_curly_apostrophe_in_name():
    # LLM returns curly apostrophe; page has straight apostrophe
    records = [
        LLMPerson(
            name="Mario D\u2019Agostino",
            other_names=[],
            roles=["council"],
            phone=None,
            email=None,
            url=None,
            designations=[],
            source_url="http://example.com",
        )
    ]
    input_text = "Council member Mario D'Agostino represents District 4."
    assert check_page_heuristics(dummy_logger(), "http://example.com", input_text, records) is True

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
    assert check_page_heuristics(dummy_logger(), "dummy-link", input_text, records) is False


def test_normalize_record_strips_whitespace_from_email():
    record = LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone=None, email="john @example.com", url=None, designations=[], source_url="test")
    result = normalize_record(dummy_logger(), record)
    assert result.email == "john@example.com"


def test_normalize_record_strips_internal_whitespace_from_email():
    record = LLMPerson(name="John Doe", other_names=[], roles=["mayor"], phone=None, email="john@ example .com", url=None, designations=[], source_url="test")
    result = normalize_record(dummy_logger(), record)
    assert result.email == "john@example.com"


def test_add_relevant_urls_includes_cross_domain():
    """Relevant URLs identified by the LLM should be added even if they are on a different domain."""
    existing_links = [
        Link(url="https://cityofbaycity.org/city-council", status=LinkStatus.DONE.value, folder_name="council"),
    ]
    mayor_url = "https://www.baycitytx.gov/296/Office-of-the-Mayor"
    result = add_relevant_urls([mayor_url], existing_links)
    pending_urls = [l.url for l in result if l.status == LinkStatus.PENDING.value]
    # URL is canonicalized: www. stripped, path lowercased
    assert "https://baycitytx.gov/296/office-of-the-mayor" in pending_urls


def test_add_relevant_urls_skips_already_present():
    existing_links = [
        Link(url="https://cityofbaycity.org/mayor", status=LinkStatus.DONE.value, folder_name="mayor"),
    ]
    result = add_relevant_urls(["https://cityofbaycity.org/mayor"], existing_links)
    assert len(result) == 1


def test_add_relevant_urls_increments_existing_pending():
    existing_links = [
        Link(url="https://cityofbaycity.org/mayor", status=LinkStatus.PENDING.value, folder_name="", num_references=1),
        Link(url="https://cityofbaycity.org/council", status=LinkStatus.PENDING.value, folder_name="", num_references=0),
    ]
    result = add_relevant_urls(["https://cityofbaycity.org/mayor"], existing_links)
    mayor = next(l for l in result if "mayor" in l.url)
    assert mayor.num_references == 2


def test_add_relevant_urls_sorts_by_num_references():
    existing_links = [
        Link(url="https://cityofbaycity.org/council", status=LinkStatus.PENDING.value, folder_name="", num_references=3),
        Link(url="https://cityofbaycity.org/mayor", status=LinkStatus.PENDING.value, folder_name="", num_references=1),
    ]
    result = add_relevant_urls(["https://cityofbaycity.org/mayor"], existing_links)
    pending = [l for l in result if l.status == LinkStatus.PENDING.value]
    # mayor now has 2 references, council has 3 — council should still be first
    assert pending[0].url == "https://cityofbaycity.org/council"
    assert pending[1].url == "https://cityofbaycity.org/mayor"

    result2 = add_relevant_urls(["https://cityofbaycity.org/mayor"], result)
    pending2 = [l for l in result2 if l.status == LinkStatus.PENDING.value]
    # mayor now has 3 references, tied with council — path depth tiebreak (same), stable order
    assert pending2[0].url == "https://cityofbaycity.org/council"

    result3 = add_relevant_urls(["https://cityofbaycity.org/mayor"], result2)
    pending3 = [l for l in result3 if l.status == LinkStatus.PENDING.value]
    # mayor now has 4 references, beats council's 3 — mayor should be first
    assert pending3[0].url == "https://cityofbaycity.org/mayor"


def test_add_relevant_urls_does_not_increment_non_pending():
    existing_links = [
        Link(url="https://cityofbaycity.org/mayor", status=LinkStatus.DONE.value, folder_name="mayor", num_references=1),
    ]
    result = add_relevant_urls(["https://cityofbaycity.org/mayor"], existing_links)
    assert len(result) == 1
    assert result[0].num_references == 1  # unchanged


def test_add_relevant_urls_no_domain_filtering():
    # add_relevant_urls does not filter by domain — that's the LLM prompt's responsibility
    existing_links = []
    result = add_relevant_urls(["https://facebook.com/baycity"], existing_links)
    assert len(result) == 1
    assert result[0].url == "https://facebook.com/baycity"


def test_add_relevant_urls_name_match_beats_more_references():
    existing_links = [
        Link(url="https://cityofbaycity.org/council", status=LinkStatus.PENDING.value, folder_name="", num_references=5),
        Link(url="https://cityofbaycity.org/655/Susan-Reardon", status=LinkStatus.PENDING.value, folder_name="", num_references=1),
    ]
    result = add_relevant_urls([], existing_links, names=["Susan Reardon"])
    pending = [l for l in result if l.status == LinkStatus.PENDING.value]
    assert pending[0].url == "https://cityofbaycity.org/655/Susan-Reardon"


def test_add_relevant_urls_designation_match_beats_more_references():
    existing_links = [
        Link(url="https://cityofbaycity.org/council", status=LinkStatus.PENDING.value, folder_name="", num_references=5),
        Link(url="https://cityofbaycity.org/position-4/seat", status=LinkStatus.PENDING.value, folder_name="", num_references=1),
    ]
    result = add_relevant_urls([], existing_links, designations=["Position 4"])
    pending = [l for l in result if l.status == LinkStatus.PENDING.value]
    assert pending[0].url == "https://cityofbaycity.org/position-4/seat"


def test_add_relevant_urls_name_match_beats_designation_match():
    existing_links = [
        Link(url="https://cityofbaycity.org/position-4/seat", status=LinkStatus.PENDING.value, folder_name="", num_references=3),
        Link(url="https://cityofbaycity.org/655/Susan-Reardon", status=LinkStatus.PENDING.value, folder_name="", num_references=1),
    ]
    result = add_relevant_urls([], existing_links, names=["Susan Reardon"], designations=["Position 4"])
    pending = [l for l in result if l.status == LinkStatus.PENDING.value]
    assert pending[0].url == "https://cityofbaycity.org/655/Susan-Reardon"


def test_add_relevant_urls_role_hint_in_url_beats_more_references():
    # "city-council" contains "council" which is a significant token of "Council Member"
    existing_links = [
        Link(url="https://cityofbaycity.org/general-info", status=LinkStatus.PENDING.value, folder_name="", num_references=5),
        Link(url="https://cityofbaycity.org/283/city-council", status=LinkStatus.PENDING.value, folder_name="", num_references=1),
    ]
    result = add_relevant_urls([], existing_links, designations=["Council Member"])
    pending = [l for l in result if l.status == LinkStatus.PENDING.value]
    assert pending[0].url == "https://cityofbaycity.org/283/city-council"


@pytest.mark.asyncio
async def test_check_page_relevance_adds_cross_domain_relevant_urls():
    """relevant_urls from check_page_relevance should be added even when on a different domain than config.url."""
    context = workflow_context_factory(steps={})
    # config.url is seattle.gov; mayor URL is on a different domain
    mayor_url = "https://seattle-mayor.gov/mayor"
    context = context.copy(update={
        "data": context.data.copy(update={
            "links": [
                Link(url="https://seattle.gov/council", status=LinkStatus.DONE.value, folder_name="council"),
            ]
        })
    })
    page = Link(url="https://seattle.gov/council", status=LinkStatus.PREPROCESSED.value, folder_name="council")
    llm_response = RelevantPageResponseSchema(is_relevant=True, relevant_urls=[mayor_url])

    with patch(
        "jobs.people_collector.steps.step_05_process_page_content.process_page_content._relevance_llm.run_prompt",
        new=AsyncMock(return_value=llm_response.model_dump()),
    ):
        updated_links, _ = await check_page_relevance(context, page, "some page content")

    pending_urls = [l.url for l in updated_links if l.status == LinkStatus.PENDING.value]
    assert mayor_url in pending_urls
