from unittest.mock import AsyncMock, patch

import pytest
from runners.pipeline03_people_collector.schemas import (
    Link,
    LinkFrontier,
    LinkStatus,
    OrganizationNeed,
    PersonSourceRecord,
    PeopleArrayLLMResponseSchema,
    ExtractedPersonRecord,
    RelevantPageResponseSchema,
)
from runners.pipeline03_people_collector.steps.step_04_process_page_content.heuristics import (
    check_page_heuristics,
    without_unnormalizable_phones,
    without_unverified_emails,
)
from runners.pipeline03_people_collector.steps.step_04_process_page_content.heuristics_failure import (
    HeuristicsFailure,
)
from runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content import (
    _resolve_candidate_urls,
    _split_content_into_chunks,
    check_page_relevance,
    process_page_content,
    process_with_llm,
)
from shared.utils.content_hash import content_hash
from runners.pipeline03_people_collector.utils.link_discovery import (
    _pending_sort_key,
    add_relevant_urls,
    anchor_texts,
    has_role_and_contact_info,
)
from runners.pipeline03_people_collector.utils.organization_terms import as_tokens, search_phrases
from shared.schemas import KnownOrganization, Post, RoleConfig, Role
from tests.factories.pipeline_run_context import pipeline_run_context_factory
from shared.utils.taxonomy import build_taxonomy
from shared.utils.url_utils import canonical_url

_ROLE_TAXONOMY = build_taxonomy(
    RoleConfig(roles=[Role(id="mayor", label="mayor"), Role(id="council", label="council")])
)


def make_frontier(*links: Link) -> LinkFrontier:
    from shared.utils.url_utils import canonical_url as _can

    lmap = {_can(l.url): l for l in links}
    queue = [k for k, l in lmap.items() if l.status == LinkStatus.PENDING.value]
    return LinkFrontier(links=lmap, queue=queue)


def pending_urls(frontier: LinkFrontier) -> list[str]:
    return [
        l.url for l in frontier.links.values() if l.status == LinkStatus.PENDING.value
    ]


def pending_in_queue_order(frontier: LinkFrontier) -> list[Link]:
    """Returns pending links in scrape priority order (queue order)."""
    return [frontier.links[k] for k in frontier.queue if k in frontier.links]


# keep old name as alias for backward compat within this file
make_links = make_frontier

pytestmark = pytest.mark.unit


def dummy_logger():
    class DummyLogger:
        def warning(self, msg):
            print(f"WARNING: {msg}")

    return DummyLogger()


def test_has_role_and_contact_info_with_valid_contact_info_and_role():
    """Test when there are at least two different types of contact info and a matching role."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="mayor",
            phone="123-456-7890",
            email="john@example.com",
            url=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="council",
            phone=None,
            email=None,
            url="http://example.com",
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == True


def test_has_role_and_contact_info_with_only_a_phone():
    """A phone or email on any record is enough, even if nothing else is known."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="mayor",
            phone="123-456-7890",
            email=None,
            url=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="council",
            phone=None,
            email=None,
            url=None,
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == True


def test_has_role_and_contact_info_with_no_matching_role():
    """Test when there is no matching role."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="teacher",
            phone="123-456-7890",
            email="john@example.com",
            url=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="engineer",
            phone=None,
            email=None,
            url="http://example.com",
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == False


def test_has_role_and_contact_info_with_distinct_urls_but_no_phone_or_email():
    """Without a phone or email, more than one distinct url still counts."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email=None,
            url="https://example.com/john",
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email=None,
            url="https://example.com/jane",
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == True


def test_has_role_and_contact_info_with_one_shared_url_and_no_phone_or_email():
    """A single url shared across the group is not enough on its own."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email=None,
            url="https://example.com/council",
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email=None,
            url="https://example.com/council",
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == False


def test_has_role_and_contact_info_with_exactly_three_contact_info_types():
    """Test when there are exactly two different types of contact info."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="mayor",
            phone="123-456-7890",
            email=None,
            url="https://example.com",
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email="jane@example.com",
            url=None,
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == True


def test_has_role_and_contact_info_with_no_contact_info():
    """Test when there is no contact info."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email=None,
            url=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email=None,
            url=None,
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == False


def test_has_role_and_contact_info_with_no_records():
    """Test when there are no records."""
    records = []
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == False


def test_has_role_and_contact_info_with_three_contact_info_types():
    """Test when there are three different types of contact info."""
    records = [
        PersonSourceRecord(
            name="John Doe",
            other_names=[],
            label="mayor",
            phone="123-456-7890",
            email="john@example.com",
            url=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="mayor",
            phone=None,
            email=None,
            url="http://example.com",
            source_url="test",
        ),
    ]
    assert has_role_and_contact_info(_ROLE_TAXONOMY, records) == True


def test_check_page_heuristics_passes_with_empty_records():
    assert (
        check_page_heuristics(dummy_logger(), "dummy-link", "Some markdown content", [])
        is None
    )


def test_check_page_heuristics_passes_with_nonempty_records():
    records = [
        PersonSourceRecord(
            name="Laura Palmer",
            other_names=[],
            label="mayor Ward 8",
            # A real number, not `555-9999`: seven digits is not a US number, and this
            # asserted True only while the retry guard missed everything phonenumbers
            # parsed-but-rejected.
            phone="856-358-2509",
            email="laura@palmer.com",
            url="http://palmer.com/laura",
            source_url="http://palmer.com",
        )
    ]
    input_text = "Laura Palmer the mayor is available at laura@palmer.com or 856-358-2509. See http://palmer.com/laura for more details."
    assert (
        check_page_heuristics(dummy_logger(), "dummy-link", input_text, records) is None
    )


@pytest.mark.parametrize("phone", ["555-555-5555", "123-4567", "000-000-0000", "869-3268"])
def test_an_invalid_phone_is_dropped_and_the_person_kept(phone):
    """These parse and are then rejected as not-real numbers; "869-3268" is Athens, Vermont's,
    written without its area code. Each used to force a retry and, after it, skip the page."""
    records = [
        PersonSourceRecord(
            name="Laura Palmer",
            label="mayor",
            phone=phone,
            source_url="http://palmer.com",
        )
    ]
    [kept], failures = without_unnormalizable_phones(dummy_logger(), "dummy-link", records)
    assert (kept.phone, kept.name, failures) == (None, "Laura Palmer", [HeuristicsFailure.PHONE_NOT_NORMALIZABLE])


def test_a_dropped_phone_no_longer_fails_the_page():
    records = [PersonSourceRecord(name="Laura Palmer", label="mayor", phone="869-3268", source_url="http://palmer.com")]
    input_text = "Laura Palmer the mayor is available at 869-3268."
    kept, _ = without_unnormalizable_phones(dummy_logger(), "dummy-link", records)
    assert check_page_heuristics(dummy_logger(), "dummy-link", input_text, kept) is None


def test_a_valid_phone_is_kept():
    records = [PersonSourceRecord(name="Laura Palmer", label="mayor", phone="802-869-3268", source_url="http://palmer.com")]
    assert without_unnormalizable_phones(dummy_logger(), "dummy-link", records) == (records, [])


def test_check_page_heuristics_fails_on_the_name_if_input_text_empty():
    records = [
        PersonSourceRecord(
            name="Laura Palmer",
            other_names=[],
            label="mayor Ward 8",
            phone="555-9999",
            email="laura@palmer.com",
            url="http://palmer.com/laura",
            source_url="http://palmer.com",
        )
    ]
    input_text = ""
    assert (
        check_page_heuristics(dummy_logger(), "dummy-link", input_text, records)
        == HeuristicsFailure.NAME_NOT_IN_TEXT
    )


def test_check_page_heuristics_fails_if_phone_not_in_text():
    records = [
        PersonSourceRecord(
            name="Pat NoPhoneInText",
            other_names=[],
            label="council Ward 2",
            phone="555-0000",
            email="pat@nophone.com",
            url="http://nophone.com/pat",
            source_url="http://nophone.com",
        )
    ]
    input_text = "Council member Pat NoPhoneInText can be reached at pat@nophone.com. See http://nophone.com/pat. Ward 2."
    # "555-0000" is not in input_text
    assert (
        check_page_heuristics(dummy_logger(), "dummy-link", input_text, records)
        == HeuristicsFailure.PHONE_NOT_IN_TEXT
    )


def test_an_email_not_in_text_is_dropped_and_the_person_kept():
    records = [
        PersonSourceRecord(
            name="Alex NoEmailInText",
            other_names=[],
            label="mayor Ward 3",
            phone="555-5678",
            email="alex@noemail.com",
            url="http://noemail.com/alex",
            source_url="http://noemail.com",
        )
    ]
    input_text = "Mayor Alex NoEmailInText is available at 555-5678 or http://noemail.com/alex. Ward 3."
    # "alex@noemail.com" is not in input_text
    [kept], failures = without_unverified_emails(dummy_logger(), "dummy-link", input_text, records)
    assert (kept.email, kept.phone, kept.name) == (None, "555-5678", "Alex NoEmailInText")
    assert failures == [HeuristicsFailure.EMAIL_NOT_IN_TEXT]


def test_an_email_is_kept_when_email_has_space_before_at_in_source():
    records = [
        PersonSourceRecord(
            name="Alexandria Inocencio",
            other_names=[],
            label="mayor",
            phone=None,
            email="alexandria.inocencio@cityofdilleytx.com",
            url=None,
            source_url="http://cityofdilleytx.com",
        )
    ]
    # Source page has broken email with space before @
    input_text = "Mayor Alexandria Inocencio  alexandria.inocencio @cityofdilleytx.com"
    assert without_unverified_emails(dummy_logger(), "dummy-link", input_text, records) == (records, [])


def test_an_email_is_kept_when_email_has_markdown_escaped_underscore():
    records = [
        PersonSourceRecord(
            name="Alfredo Macedo",
            other_names=[],
            label="council member",
            phone=None,
            email="amacedo_84@hotmail.com",
            url=None,
            source_url="http://cityofmcgregor.com",
        )
    ]
    # Markdown escapes the underscore as \_
    input_text = "Council Member Alfredo Macedo  amacedo\\_84@hotmail.com"
    assert without_unverified_emails(dummy_logger(), "dummy-link", input_text, records) == (records, [])


def test_an_email_is_kept_when_mailto_href_splits_tld():
    # CMS bug: <a href="mailto:user@domain.tx">user@domain.tx</a> .us
    # LLM reconstructs the full email; heuristic must find it despite the split
    records = [
        PersonSourceRecord(
            name="Joseph Smith",
            other_names=[],
            label="council member District 1",
            phone=None,
            email="district1@ci.lamesa.tx.us",
            url=None,
            source_url="http://ci.lamesa.tx.us",
        )
    ]
    input_text = "Joseph Smith, District 1  [district1@ci.lamesa.tx](mailto:district1@ci.lamesa.tx) .us"
    assert without_unverified_emails(dummy_logger(), "dummy-link", input_text, records) == (records, [])


def test_an_email_without_an_at_sign_is_dropped():
    # Alnum fallback must not match if there is no @ in the normalized email
    records = [
        PersonSourceRecord(
            name="Jane Doe",
            other_names=[],
            label="council member",
            phone=None,
            email="notanemail",
            url=None,
            source_url="http://example.com",
        )
    ]
    input_text = "Jane Doe council member notanemail"
    [kept], failures = without_unverified_emails(dummy_logger(), "dummy-link", input_text, records)
    assert (kept.email, failures) == (None, [HeuristicsFailure.EMAIL_NOT_IN_TEXT])


def test_check_page_heuristics_matches_name_with_curly_apostrophe_in_text():
    # LLM returns straight apostrophe; page has curly right-single-quote (U+2019)
    records = [
        PersonSourceRecord(
            name="Mario D'Agostino",
            other_names=[],
            label="council",
            phone=None,
            email=None,
            url=None,
            source_url="http://example.com",
        )
    ]
    input_text = "Council member Mario D\u2019Agostino represents District 4."
    assert (
        check_page_heuristics(dummy_logger(), "http://example.com", input_text, records)
        is None
    )


def test_check_page_heuristics_matches_name_with_curly_apostrophe_in_name():
    # LLM returns curly apostrophe; page has straight apostrophe
    records = [
        PersonSourceRecord(
            name="Mario D\u2019Agostino",
            other_names=[],
            label="council",
            phone=None,
            email=None,
            url=None,
            source_url="http://example.com",
        )
    ]
    input_text = "Council member Mario D'Agostino represents District 4."
    assert (
        check_page_heuristics(dummy_logger(), "http://example.com", input_text, records)
        is None
    )


def test_check_page_heuristics_matches_name_split_across_lines():
    # HTML-to-markdown sometimes breaks a name mid-word at a line boundary
    records = [
        PersonSourceRecord(
            name="Martin Mattessich",
            other_names=[],
            label="council",
            phone=None,
            email=None,
            url=None,
            source_url="http://example.com",
        )
    ]
    input_text = "Councilman Marti\nn Mattessich serves on the council."
    assert (
        check_page_heuristics(dummy_logger(), "http://example.com", input_text, records)
        is None
    )


def test_check_page_heuristics_fails_if_url_not_in_text():
    records = [
        PersonSourceRecord(
            name="Jamie NoUrlInText",
            other_names=[],
            label="council Ward 4",
            # A real number: `555-8765` failed as not normalizable, so this never reached the url.
            phone="856-358-2509",
            email="jamie@nourl.com",
            url="http://nourl.com/jamie",
            source_url="http://nourl.com",
        )
    ]
    input_text = "Council member Jamie NoUrlInText can be reached at jamie@nourl.com or 856-358-2509. Ward 4."
    # "http://nourl.com/jamie" is not in input_text
    assert (
        check_page_heuristics(dummy_logger(), "dummy-link", input_text, records)
        == HeuristicsFailure.URL_NOT_IN_TEXT
    )


def test_a_compound_phone_is_dropped_and_the_person_kept():
    """Two numbers in one field is the model ignoring the prompt's one-phone precedence. It
    used to force a re-read, and a page that kept doing it was skipped; now only the field goes."""
    records = [
        PersonSourceRecord(
            name="Alice Boroughman",
            other_names=[],
            label="mayor",
            phone="856-358-2509 or 856-358-4010 Ext. 112",
            email=None,
            url=None,
            source_url="http://example.com",
        )
    ]
    [kept], failures = without_unnormalizable_phones(dummy_logger(), "http://example.com", records)
    assert (kept.phone, kept.name, failures) == (None, "Alice Boroughman", [HeuristicsFailure.PHONE_NOT_NORMALIZABLE])


def test_add_relevant_urls_includes_same_domain():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/city-council",
            status=LinkStatus.DONE.value,
            folder_name="council",
        )
    )
    result = add_relevant_urls(
        ["https://www.cityofbaycity.org/296/Office-of-the-Mayor"],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
    )
    assert "https://www.cityofbaycity.org/296/Office-of-the-Mayor" in pending_urls(
        result
    )


def test_add_relevant_urls_filters_cross_domain():
    result = add_relevant_urls(
        ["https://www.baycitytx.gov/296/Office-of-the-Mayor"],
        LinkFrontier(),
        domain="https://cityofbaycity.org",
        needs=[],
    )
    assert len(result) == 0


def test_add_relevant_urls_skips_already_present():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/mayor",
            status=LinkStatus.DONE.value,
            folder_name="mayor",
        )
    )
    result = add_relevant_urls(
        ["https://cityofbaycity.org/mayor"],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
    )
    assert len(result) == 1


def test_add_relevant_urls_increments_existing_pending():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/mayor",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
        Link(
            url="https://cityofbaycity.org/council",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=0,
        ),
    )
    result = add_relevant_urls(
        ["https://cityofbaycity.org/mayor"],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
    )
    assert result.get("https://cityofbaycity.org/mayor").num_references == 2


def test_add_relevant_urls_sorts_by_num_references():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/council",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=3,
        ),
        Link(
            url="https://cityofbaycity.org/mayor",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    r1 = add_relevant_urls(
        ["https://cityofbaycity.org/mayor"],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
    )
    p = pending_in_queue_order(r1)
    assert p[0].url == "https://cityofbaycity.org/council"
    assert p[1].url == "https://cityofbaycity.org/mayor"

    r2 = add_relevant_urls(
        ["https://cityofbaycity.org/mayor"], r1, domain="https://cityofbaycity.org", needs=[]
    )
    assert pending_in_queue_order(r2)[0].url == "https://cityofbaycity.org/council"

    r3 = add_relevant_urls(
        ["https://cityofbaycity.org/mayor"], r2, domain="https://cityofbaycity.org", needs=[]
    )
    assert pending_in_queue_order(r3)[0].url == "https://cityofbaycity.org/mayor"


def test_add_relevant_urls_does_not_increment_non_pending():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/mayor",
            status=LinkStatus.DONE.value,
            folder_name="mayor",
            num_references=1,
        )
    )
    result = add_relevant_urls(
        ["https://cityofbaycity.org/mayor"],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
    )
    assert len(result) == 1
    assert result.get("https://cityofbaycity.org/mayor").num_references == 1


def test_add_relevant_urls_keyword_beats_name_match():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/council",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=5,
        ),
        Link(
            url="https://cityofbaycity.org/655/Susan-Reardon",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    result = add_relevant_urls(
        [], frontier, domain="https://cityofbaycity.org", needs=[], names=["Susan Reardon"]
    )
    assert pending_in_queue_order(result)[0].url == "https://cityofbaycity.org/council"


def test_add_relevant_urls_keyword_beats_designation_match():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/directory",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=5,
        ),
        Link(
            url="https://cityofbaycity.org/position-4/seat",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    result = add_relevant_urls(
        [], frontier, domain="https://cityofbaycity.org", needs=[], designations=["Position 4"]
    )
    assert pending_in_queue_order(result)[0].url == "https://cityofbaycity.org/directory"


def test_add_relevant_urls_ranks_an_organizations_page_by_its_post_labels():
    """No role word is a common keyword any more; the council's page ranks because "Council
    Member" is one of the council's own post labels."""
    council = KnownOrganization(
        id="council",
        name="City Council",
        posts=[
            Post(
                id="post",
                jurisdiction_ocdid="ocd-jurisdiction/country:us/state:zz/place:bay_city/government",
                organization_id="council",
                role_id="council-member",
                division_ocdid="ocd-division/country:us/state:zz/place:bay_city",
                label="Council Member",
                role_label="Council Member",
            )
        ],
    )
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/news/latest",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=5,
        ),
        Link(
            url="https://cityofbaycity.org/council",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    result = add_relevant_urls(
        [],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
        designations=as_tokens(search_phrases([council], [])),
    )
    assert pending_in_queue_order(result)[0].url == "https://cityofbaycity.org/council"


def test_add_relevant_urls_serves_the_neediest_organization_first():
    """The council is complete and its bios are linked from every council page; the mayor is
    not found yet, so the mayor's one link goes first."""
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/council/members/ana",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=9,
        ),
        Link(
            url="https://cityofbaycity.org/mayor",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    needs = [
        OrganizationNeed(organization_id="council", shortfall=0.0, terms=["council"], missing_terms=[]),
        OrganizationNeed(
            organization_id="mayor", shortfall=1.0, terms=["mayor"], missing_terms=["mayor"]
        ),
    ]

    result = add_relevant_urls([], frontier, domain="https://cityofbaycity.org", needs=needs)

    assert pending_in_queue_order(result)[0].url == "https://cityofbaycity.org/mayor"


def test_add_relevant_urls_ranks_a_missing_post_within_its_organization():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/council/meetings",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=5,
        ),
        Link(
            url="https://cityofbaycity.org/council/mayor",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    needs = [
        OrganizationNeed(
            organization_id="council",
            shortfall=0.25,
            terms=["council", "member", "mayor"],
            missing_terms=["mayor"],
        )
    ]

    result = add_relevant_urls([], frontier, domain="https://cityofbaycity.org", needs=needs)

    assert pending_in_queue_order(result)[0].url == "https://cityofbaycity.org/council/mayor"


def test_add_relevant_urls_matches_organizations_on_the_path_not_the_domain():
    """"Bay City Council" must not make every link on cityofbaycity.org the council's."""
    link = Link(url="https://cityofbaycity.org/news", status=LinkStatus.PENDING.value)
    need = OrganizationNeed(
        organization_id="council", shortfall=1.0, terms=["cityofbaycity"], missing_terms=[]
    )

    assert _pending_sort_key(link, [need], [], [])[0] == 0.0


def test_add_relevant_urls_name_match_beats_designation_match():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/position-4/seat",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
        Link(
            url="https://cityofbaycity.org/655/Susan-Reardon",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    result = add_relevant_urls(
        [],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
        names=["Susan Reardon"],
    )
    assert (
        pending_in_queue_order(result)[0].url
        == "https://cityofbaycity.org/655/Susan-Reardon"
    )


def test_add_relevant_urls_role_hint_in_url_beats_more_references():
    frontier = make_frontier(
        Link(
            url="https://cityofbaycity.org/general-info",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=5,
        ),
        Link(
            url="https://cityofbaycity.org/283/city-council",
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
        ),
    )
    result = add_relevant_urls(
        [],
        frontier,
        domain="https://cityofbaycity.org",
        needs=[],
    )
    assert (
        pending_in_queue_order(result)[0].url
        == "https://cityofbaycity.org/283/city-council"
    )


@pytest.mark.asyncio
async def test_check_page_relevance_filters_cross_domain_relevant_urls():
    """relevant_urls from check_page_relevance on a different domain than the page should be excluded."""
    context = pipeline_run_context_factory(steps={})
    # page is on seattle.gov; this URL is on a different domain
    cross_domain_url = "https://seattle-mayor.gov/mayor"
    same_domain_url = "https://seattle.gov/city-council"
    frontier = make_frontier(
        Link(
            url="https://seattle.gov/council",
            status=LinkStatus.DONE.value,
            folder_name="council",
        )
    )
    context = context.model_copy(
        update={"data": context.data.model_copy(update={"frontier": frontier})}
    )
    page = Link(
        url="https://seattle.gov/council",
        status=LinkStatus.PREPROCESSED.value,
        folder_name="council",
    )
    llm_response = RelevantPageResponseSchema(
        is_relevant=True, relevant_urls=[cross_domain_url, same_domain_url]
    )

    with patch(
        "runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content.open_router_llm.run_prompt",
        new=AsyncMock(return_value=llm_response.model_dump()),
    ):
        result_frontier, _ = await check_page_relevance(
            context, page, "some page content", [], [], []
        )

    result_pending_urls = pending_urls(result_frontier)
    assert cross_domain_url not in result_pending_urls
    assert "https://seattle.gov/city-council" in result_pending_urls


_LLM = "runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content"


def _context_with_page(page: Link):
    context = pipeline_run_context_factory(steps={})
    return context.model_copy(
        update={"data": context.data.model_copy(update={"frontier": make_frontier(page)})}
    )


@pytest.mark.asyncio
async def test_the_relevance_verdict_is_kept_on_the_link_with_every_url_the_llm_proposed():
    """Unfiltered: the cross-domain url never reaches the queue, but a replay re-filters."""
    page = Link(url="https://seattle.gov/council", status=LinkStatus.PREPROCESSED.value)
    proposed = ["https://seattle-mayor.gov/mayor", "https://seattle.gov/city-council"]
    llm_response = RelevantPageResponseSchema(is_relevant=True, relevant_urls=proposed)

    with patch(f"{_LLM}.open_router_llm.run_prompt", new=AsyncMock(return_value=llm_response.model_dump())):
        frontier, _ = await check_page_relevance(_context_with_page(page), page, "text", [], [], [])

    link = frontier.get(page.url)
    assert (link.is_relevant, link.relevant_urls) == (True, proposed)


@pytest.mark.asyncio
async def test_an_irrelevant_page_still_gets_both_hashes(tmp_path):
    """The gate needs them most for pages judged irrelevant: those skip everything next time."""
    page = Link(
        url="https://seattle.gov/parks", status=LinkStatus.PREPROCESSED.value, folder_name="parks"
    )
    (tmp_path / "parks").mkdir()
    (tmp_path / "parks" / "preprocessed.md").write_text("# Parks", encoding="utf-8")
    llm_response = RelevantPageResponseSchema(is_relevant=False, relevant_urls=[])

    with (
        patch(f"{_LLM}.data_path_utils.get_cache_path", return_value=str(tmp_path)),
        patch(f"{_LLM}.open_router_llm.run_prompt", new=AsyncMock(return_value=llm_response.model_dump())),
    ):
        frontier, _ = await process_page_content(_context_with_page(page), page)

    link = frontier.get(page.url)
    assert link.status == LinkStatus.PROCESSED_IRRELEVANT.value
    assert link.is_relevant is False
    assert link.page_hash == content_hash("# Parks")
    assert link.prompt_hash is not None


def test_split_content_into_chunks_no_split_when_fits():
    content = "## Section\n\nSome content here."
    chunks = _split_content_into_chunks(content, max_chars=10_000)
    assert chunks == [content]


def test_split_content_into_chunks_splits_large_content():
    # Each section is ~300 chars; max_chars = 2000 keeps the overlap (500) well within capacity
    section = (
        "## Councilmember Jane Smith\n\n"
        + "Contact: 555-1234, jane@city.gov. " * 8
        + "\n\n"
    )
    content = section * 20  # ~6000 chars total
    max_chars = 2_000
    chunks = _split_content_into_chunks(content, max_chars=max_chars)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= max_chars + 500  # tolerance for overlap


def test_split_content_into_chunks_overlap_carries_context():
    # Each section is ~300 chars; max_chars fits ~3 sections, overlap carries context across boundaries
    sections = [
        f"## Member {i}\n\n" + f"Email: member{i}@city.gov. " * 10 + "\n\n"
        for i in range(10)
    ]
    content = "".join(sections)
    max_chars = 2_000
    chunks = _split_content_into_chunks(content, max_chars=max_chars)
    assert len(chunks) > 1
    # The tail of chunk 0 should appear somewhere in chunk 1 (overlap)
    assert chunks[0][-100:].strip() in chunks[1]


@pytest.mark.asyncio
async def test_process_with_llm_reorders_inverted_names():
    """Names in 'Last, First' format are reordered at ingest, before grouping."""
    llm_response = PeopleArrayLLMResponseSchema(
        people=[
            ExtractedPersonRecord(
                name="Kincannon, Laurie", label="Mayor"
            ),
            ExtractedPersonRecord(
                name="Burke, Rory", label="Councilman Position 4"
            ),
        ]
    )

    with patch(
        "runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content.open_router_llm.run_prompt",
        new=AsyncMock(return_value=llm_response),
    ):
        records = await process_with_llm(
            "https://city.gov/council",
            "test-request",
            "ocd-jurisdiction/country:us/state:tx/place:port_isabel/government",
            "page content",
            "prompt",
            [],
        )

    assert [r.name for r in records] == ["Laurie Kincannon", "Rory Burke"]


@pytest.mark.asyncio
async def test_process_with_llm_resolves_a_shortened_url_against_its_page():
    llm_response = PeopleArrayLLMResponseSchema(
        people=[
            ExtractedPersonRecord(name="Rod Dembowski", label="Council Member", url="/en/council/rod-dembowski"),
            ExtractedPersonRecord(name="Rhonda Lewis", label="Council Member", url="https://kingcounty.gov/en/council/rhonda-lewis"),
        ]
    )

    with patch(
        "runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content.open_router_llm.run_prompt",
        new=AsyncMock(return_value=llm_response),
    ):
        records = await process_with_llm(
            "https://kingcounty.gov/en/elected-officials",
            "test-request",
            "ocd-jurisdiction/country:us/state:wa/county:king/government",
            "page content",
            "prompt",
            [],
        )

    assert [r.url for r in records] == [
        "https://kingcounty.gov/en/council/rod-dembowski",
        "https://kingcounty.gov/en/council/rhonda-lewis",
    ]


@pytest.mark.asyncio
async def test_process_with_llm_keeps_only_downloaded_images():
    """Seattle, 2026-09-19: a relative src the downloader skipped, and a `local://` hash the
    extractor wrapped in a made-up url, each outvoted a real photo at ingest."""
    llm_response = PeopleArrayLLMResponseSchema(
        people=[
            ExtractedPersonRecord(name="Rob Saka", label="Mayor", image="local://8ac384d14474.png"),
            ExtractedPersonRecord(
                name="Joy Hollingsworth", label="Mayor", image="/images/hollingsworth-family.jpeg"
            ),
            ExtractedPersonRecord(
                name="Debora Juarez", label="Mayor", image="https://seattle.gov/domain/31ed0e44b6dc.png"
            ),
        ]
    )

    with patch(
        "runners.pipeline03_people_collector.steps.step_04_process_page_content.process_page_content.open_router_llm.run_prompt",
        new=AsyncMock(return_value=llm_response),
    ):
        records = await process_with_llm(
            "https://seattle.gov/council",
            "test-request",
            "ocd-jurisdiction/country:us/state:wa/place:seattle/government",
            "page content",
            "prompt",
            [],
        )

    assert [r.image for r in records] == ["local://8ac384d14474.png", None, None]


def test_a_link_the_llm_picked_carries_its_text_from_the_page():
    url = "https://cityofbaycity.org/296/Office-of-the-Mayor"
    content = f"Read about the [Office of the Mayor]({url}) and the [council](https://cityofbaycity.org/council)."
    response = RelevantPageResponseSchema(is_relevant=True, relevant_urls=[url])

    urls, comments = _resolve_candidate_urls(
        response, "https://cityofbaycity.org/", content, [], None, [], dummy_logger()
    )

    assert urls == [url]
    assert comments == {url: (None, "Office of the Mayor")}


def test_a_link_the_llm_shortened_to_its_path_is_resolved_against_the_page():
    """Rowley's homepage: every link the model picked came back as a path and was dropped."""
    page_url = "https://www.townofrowley.net/"
    full = "https://www.townofrowley.net/board-selectmen"
    content = f"See the [Board of Selectmen]({full})."
    response = RelevantPageResponseSchema(is_relevant=False, relevant_urls=["/board-selectmen"])

    urls, comments = _resolve_candidate_urls(response, page_url, content, [], None, [], dummy_logger())

    assert urls == [full]
    assert comments == {full: (None, "Board of Selectmen")}


def test_anchor_texts_skip_empty_link_text():
    content = "[](https://a.gov/x) [Council](https://a.gov/x) [ ](https://a.gov/y)"

    assert anchor_texts(content) == {canonical_url("https://a.gov/x"): "Council"}
