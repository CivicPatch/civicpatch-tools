"""Collapsing one person's records into one `Person`.

Which records land in a group is `test_people_derivation.py`; this is what happens once
they have.
"""

from unittest.mock import MagicMock

import pytest
from core.people_derivation import (
    canonical_name,
    get_source_urls,
    merge_field,
    merge_labels,
    merge_records_to_person,
    merge_weak_tie_groups,
    normalize_record,
)
from shared.schemas import PersonRecord, Role, RoleConfig
from shared.utils.taxonomy import build_taxonomy

pytestmark = pytest.mark.unit

ROLE_CONFIG = RoleConfig(
    roles=[
        Role(id="mayor", label="Mayor", is_unique=True),
        Role(id="mayor-pro-tempore", label="Mayor Pro Tempore", is_unique=True),
        # `councilmember` is a real alias in the live taxonomy; without it here the
        # dedupe test would be asserting against a taxonomy no jurisdiction has.
        Role(id="council-member", label="Council Member", aliases=["councilmember"]),
        Role(id="commissioner", label="Commissioner"),
        Role(id="treasurer", label="Treasurer", is_unique=True),
    ]
)


TAXONOMY = build_taxonomy(ROLE_CONFIG)


def make_llm_person(name, label="", phone=None, email=None, url=None, source_url=None):
    return PersonRecord(
        name=name,
        label=label,
        phone=phone,
        email=email,
        url=url,
        start_date=None,
        end_date=None,
        image=None,
        source_url=source_url or f"http://source-{name.replace(' ', '').lower()}.com",
    )


def _normalize(record: PersonRecord) -> PersonRecord:
    return normalize_record(MagicMock(), record)


# --- field mergers ---


def test_merge_field():
    """Test merging single value fields"""
    result = merge_field(["555-1234", "555-1234"])
    assert result == "555-1234"


def test_canonical_name_prefers_the_name_we_already_know():
    """Measured on dev 2026-08-25: every sighting of one Seattle councilmember spelled her
    "Katie B. Wilson", but she is published as "Katie Wilson". Frequency alone renames her on
    every scrape — the identity is what stops that."""
    records = [make_llm_person("Katie B. Wilson") for _ in range(3)]

    assert canonical_name("Katie Wilson", records) == "Katie Wilson"


def test_canonical_name_takes_the_most_frequent_spelling_of_a_stranger():
    """Nobody has published them yet, so there is no human answer to defer to."""
    records = [
        make_llm_person("Bob Kettle"),
        make_llm_person("Robert Kettle"),
        make_llm_person("Bob Kettle"),
    ]

    assert canonical_name("", records) == "Bob Kettle"


def test_canonical_name_reports_nothing_when_nothing_is_spelled():
    assert canonical_name("", [make_llm_person("")]) == ""


def test_merge_labels():
    """One label per record, so merging is deduplication across the group."""
    p1 = make_llm_person("Sam", label="Council Member - Ward 1")
    p2 = make_llm_person("Sam", label="Mayor")
    p3 = make_llm_person("Sam", label="Council Member - Ward 1")
    result = merge_labels([p1, p2, p3], TAXONOMY)
    assert set(result) == {"Council Member - Ward 1", "Mayor"}


def test_merge_labels_collapses_two_spellings_of_one_office():
    """The reason the dedupe moved onto the parse. Both parse to the same role and division,
    so keeping both showed one person as holding two offices — which is what `office.name`
    joining them made unreadable in the first place."""
    p1 = make_llm_person("Sam", label="Councilmember Ward 1")
    p2 = make_llm_person("Sam", label="Council Member Ward 1")
    assert len(merge_labels([p1, p2], TAXONOMY)) == 1


def test_merge_labels_keeps_a_label_whose_parse_differs():
    """Only identical statements collapse. Residue the parser could not place is a difference,
    so a label carrying it survives rather than being silently dropped for a shorter twin."""
    p1 = make_llm_person("Sam", label="Council Member Ward 1")
    p2 = make_llm_person("Sam", label="Council Member Ward 1 (Zoning Administrator)")
    assert len(merge_labels([p1, p2], TAXONOMY)) == 2


def test_merge_labels_skips_empty():
    p1 = make_llm_person("Dana", label="")
    p2 = make_llm_person("Dana", label="Ward 2")
    assert merge_labels([p1, p2], TAXONOMY) == ["Ward 2"]


# --- normalize_record ---


def test_normalize_record_strips_whitespace_from_email():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="john @example.com",
        url=None,
        source_url="test",
    )
    assert _normalize(record).email == "john@example.com"


def test_normalize_record_strips_internal_whitespace_from_email():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="john@ example .com",
        url=None,
        source_url="test",
    )
    assert _normalize(record).email == "john@example.com"


def test_normalize_record_moves_url_from_email_to_url_when_url_empty():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="https://example.com/contact",
        url=None,
        source_url="test",
    )
    result = _normalize(record)
    assert result.email is None
    assert result.url == "https://example.com/contact"


def test_normalize_record_clears_url_from_email_when_url_already_set():
    record = PersonRecord(
        name="John Doe",
        label="mayor",
        phone=None,
        email="https://example.com/contact-form",
        url="https://example.com/bio",
        source_url="test",
    )
    result = _normalize(record)
    assert result.email is None
    assert result.url == "https://example.com/bio"


def test_normalize_record_drops_a_compound_phone_rather_than_picking_one():
    """Was `..._takes_first`, asserting `(856) 358-2509`.

    It now asserts None. Choosing between two numbers the page gave us is a guess, and the
    heuristics guard rejects the extraction upstream anyway — so a record reaching here with
    two numbers is a bug to surface, not one to paper over."""
    record = PersonRecord(
        name="Alice Boroughman",
        label="mayor",
        phone="856-358-2509 or 856-358-4010 Ext. 112",
        email=None,
        url=None,
        source_url="http://example.com",
    )
    assert _normalize(record).phone is None


# --- merge_records_to_person ---


def test_merge_records_to_person():
    p1 = make_llm_person(
        name="Eve",
        label="Council Member - Ward 5",
        phone="(956) 943-2682",
        email="eve@city.org",
        source_url="http://source1.com",
    )
    p2 = make_llm_person(
        name="Eve",
        label="Treasurer - Ward 6",
        phone="(956) 943-2682",
        email="eve@city.org",
        source_url="http://source2.com",
    )
    result = merge_records_to_person(
        MagicMock(), "Eve", [p1, p2], "jurisdiction_id", TAXONOMY
    )

    assert result.name == "Eve"
    assert set(result.labels) == {"Council Member - Ward 5", "Treasurer - Ward 6"}
    assert set(result.phones) == {"(956) 943-2682"}
    assert set(result.emails) == {"eve@city.org"}
    assert set(result.source_urls) == {"http://source1.com", "http://source2.com"}
    assert result.jurisdiction_ocdid == "jurisdiction_id"


# --- get_source_urls ---


def test_get_source_urls_credits_every_page_the_person_was_seen_on():
    """r3 repeats what r1 already said. It used to be dropped for that — but the drop was
    "whichever record came first", and read order is not ingest order. Measured on dev, it
    also cost 19 of 60 people their own bio page, beaten to a label by a listing page."""
    r1 = PersonRecord(
        name="Robert Kubert",
        label="Mayor - Ward 1",
        phone=None,
        email=None,
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r1",
    )
    r2 = PersonRecord(
        name="Robert Kubert",
        label="Council Member - Ward 2",
        phone="555-0002",
        email="mayor2@bayonne.org",
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r2",
    )
    r3 = PersonRecord(
        name="Robert Kubert",
        label="Mayor - Ward 1",
        phone=None,
        email=None,
        url="https://www.bayonnenj.org/officials/bio/mayor-robert-kubert",
        start_date=None,
        end_date=None,
        image=None,
        source_url="https://www.bayonnenj.org/r3",
    )

    assert get_source_urls([r1, r2, r3]) == [
        "https://www.bayonnenj.org/r1",
        "https://www.bayonnenj.org/r2",
        "https://www.bayonnenj.org/r3",
    ]


def test_the_merge_does_not_depend_on_the_order_records_arrive_in():
    """Ingest reads records in page order and the read reads them in row order, so anything
    order-dependent makes the two disagree — and re-publishing an unchanged roster rewrite the
    file."""
    records = [
        make_llm_person("Eve Adams", label="Mayor", phone="(956) 943-2682",
                        source_url="http://a.gov/roster"),
        make_llm_person("Eve Adams", label="Treasurer", email="eve@a.gov",
                        source_url="http://a.gov/eve"),
        make_llm_person("Eve A. Adams", label="Mayor", source_url="http://a.gov/about"),
    ]
    forwards = merge_records_to_person(
        MagicMock(), "Eve Adams", records, "ocdid", TAXONOMY
    )
    backwards = merge_records_to_person(
        MagicMock(), "Eve Adams", list(reversed(records)), "ocdid", TAXONOMY
    )

    assert forwards.model_dump(exclude={"updated_at"}) == backwards.model_dump(
        exclude={"updated_at"}
    )
    assert forwards.labels == ["Mayor", "Treasurer"]
    assert forwards.other_names == ["Eve A. Adams"]
    assert forwards.source_urls == [
        "http://a.gov/about",
        "http://a.gov/eve",
        "http://a.gov/roster",
    ]


# --- merge_weak_tie_groups ---


class TestMergeWeakTieGroups:
    def test_merges_by_last_name_and_role(self):
        """Last-name-only canonical merges into full-name canonical with same role."""
        groups = {
            "Lindamood": [make_llm_person("Lindamood", label="mayor")],
            "Bobby Lindamood": [
                make_llm_person("Bobby Lindamood", label="mayor", email="b@city.gov")
            ],
        }
        result = merge_weak_tie_groups(groups, build_taxonomy(ROLE_CONFIG))
        assert "Lindamood" not in result
        assert "Bobby Lindamood" in result
        assert len(result["Bobby Lindamood"]) == 2

    def test_merges_by_last_name_role_and_designation(self):
        """Last-name-only canonical merges when role AND designation match."""
        groups = {
            "Elder": [make_llm_person("Elder", label="mayor pro tempore - place 1")],
            "Brandi Elder": [
                make_llm_person(
                    "Brandi Elder",
                    label="mayor pro tempore - place 1",
                )
            ],
        }
        result = merge_weak_tie_groups(groups, build_taxonomy(ROLE_CONFIG))
        assert "Elder" not in result
        assert len(result["Brandi Elder"]) == 2

    def test_no_merge_when_role_differs(self):
        """Same last name but different roles — must not merge."""
        groups = {
            "Smith": [make_llm_person("Smith", label="mayor")],
            "John Smith": [make_llm_person("John Smith", label="council member")],
        }
        result = merge_weak_tie_groups(groups, build_taxonomy(ROLE_CONFIG))
        assert "Smith" in result
        assert "John Smith" in result

    def test_no_merge_when_designation_differs(self):
        """Same last name and role but different designation — must not merge."""
        groups = {
            "Smith": [make_llm_person("Smith", label="council member - place 2")],
            "John Smith": [
                make_llm_person("John Smith", label="council member - place 4")
            ],
        }
        result = merge_weak_tie_groups(groups, build_taxonomy(ROLE_CONFIG))
        assert "Smith" in result

    def test_no_merge_when_no_roles(self):
        """Last-name-only group with no roles is not merged."""
        groups = {
            "Smith": [make_llm_person("Smith")],
            "John Smith": [make_llm_person("John Smith", label="mayor")],
        }
        result = merge_weak_tie_groups(groups, build_taxonomy(ROLE_CONFIG))
        assert "Smith" in result

    def test_full_name_groups_not_treated_as_weak(self):
        """Two full-name groups sharing a last name are not merged."""
        groups = {
            "Marty C Smith Jr": [make_llm_person("Marty C Smith Jr", label="mayor")],
            "Marty D Smith Sr": [
                make_llm_person("Marty D Smith Sr", label="council member")
            ],
        }
        result = merge_weak_tie_groups(groups, build_taxonomy(ROLE_CONFIG))
        assert len(result) == 2

    def test_suffix_does_not_confuse_last_name_extraction(self):
        """A last-name-only group still resolves correctly against a suffixed full name."""
        groups = {
            "Smith": [make_llm_person("Smith", label="mayor")],
            "Marty C Smith Jr": [make_llm_person("Marty C Smith Jr", label="mayor")],
        }
        result = merge_weak_tie_groups(groups, build_taxonomy(ROLE_CONFIG))
        assert "Smith" not in result
        assert len(result["Marty C Smith Jr"]) == 2
