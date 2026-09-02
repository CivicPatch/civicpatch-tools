import pytest
from unittest.mock import MagicMock

from shared.schemas import PersonSourceRecord, Role, RoleConfig, RoleStatus
from shared.utils.merge_utils import (
    append_to_people_by_name,
    are_names_similar,
    group_people_by_name,
    has_name_overlap,
    find_indexed_name,
    is_weakly_tied,
    normalize_name,
    to_field_set_from_record,
)
from shared.utils.taxonomy import build_taxonomy

# `is_weakly_tied` resolves labels through the taxonomy rather than comparing raw strings,
# so the roles these tests use have to exist in it.
_TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(
                id="mayor",
                label="Mayor",
                status=RoleStatus.ACTIVE,
                aliases=[],
                priority=10,
                is_unique=True,
            ),
            Role(
                id="council",
                label="Council",
                status=RoleStatus.ACTIVE,
                aliases=[],
                priority=500,
                is_unique=False,
            ),
        ]
    )
)


def test_normalize_name():
    assert normalize_name("John Doe") == "John Doe"
    assert normalize_name("  Jane Smith  ") == "Jane Smith"


def test_append_to_people_by_name():
    people_by_name = {
        "John Doe": [
            PersonSourceRecord(
                name="John Doe",
                label="",
                phone_number=None,
                email=None,
                website=None,
                start_date=None,
                end_date=None,
                source_url="test",
            )
        ]
    }
    new_people = [
        PersonSourceRecord(
            name="Johnny Doe",
            label="",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        )
    ]

    updated_people_by_name = append_to_people_by_name(
        people_by_name, "John Doe", new_people
    )
    assert len(updated_people_by_name["John Doe"]) == 2

    updated_people_by_name = append_to_people_by_name(
        people_by_name, "Jane Smith", new_people
    )
    assert "Jane Smith" in updated_people_by_name
    assert len(updated_people_by_name["Jane Smith"]) == 1

    assert len(updated_people_by_name["John Doe"]) == 2
    assert len(updated_people_by_name["Jane Smith"]) == 1


def test_group_people_by_name_basic():
    """Test basic grouping of people with no existing mappings"""
    known_mappings = {}
    people_by_name = {}
    people_to_link = [
        PersonSourceRecord(
            name="John Doe",
            label="Mayor",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Smith",
            label="Council",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
    ]

    updated_people = group_people_by_name(
        known_mappings, people_by_name, people_to_link
    )
    assert "John Doe" in updated_people
    assert "Jane Smith" in updated_people


def test_group_people_by_name_with_known_mappings():
    """Test grouping with existing known mappings."""
    known_mappings = {"John Doe": ["J. Doe", "Johnny"]}
    people_by_name = {}
    people_to_link = [
        PersonSourceRecord(
            name="J. Doe",
            label="Mayor",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Johnny",
            label="Council",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
    ]

    updated_people = group_people_by_name(
        known_mappings, people_by_name, people_to_link
    )

    assert len(updated_people["John Doe"]) == 2


def test_group_people_by_name_with_existing_people():
    """Test grouping with existing people_by_name"""
    known_mappings = {}
    people_by_name = {
        "John Doe": [
            PersonSourceRecord(
                name="John Doe",
                label="Existing",
                phone_number=None,
                email=None,
                website=None,
                start_date=None,
                end_date=None,
                source_url="test",
            )
        ]
    }
    people_to_link = [
        PersonSourceRecord(
            name="John Doe",
            label="Mayor",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        )
    ]

    updated_people = group_people_by_name(
        known_mappings, people_by_name, people_to_link
    )

    assert len(updated_people["John Doe"]) == 2


def test_group_people_by_name_similarity_matching():
    """Test grouping with name similarity matching"""
    known_mappings = {}
    people_by_name = {
        "John Doe": [
            PersonSourceRecord(
                name="John Doe",
                label="Existing",
                phone_number=None,
                email=None,
                website=None,
                start_date=None,
                end_date=None,
                source_url="test",
            )
        ]
    }
    people_to_link = [
        PersonSourceRecord(
            name="Jon Doe",
            label="Mayor",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        )
    ]

    updated_people = group_people_by_name(
        known_mappings, people_by_name, people_to_link
    )

    # OK to have them separate -- this is used just for process_page_content
    assert len(updated_people.keys()) == 2
    assert "John Doe" in updated_people
    assert "Jon Doe" in updated_people


def test_group_people_by_name_deduplication():
    """Test that duplicate names are deduplicated and sorted."""
    known_mappings = {"John Doe": ["Johnny"]}
    people_by_name = {}
    people_to_link = [
        PersonSourceRecord(
            name="John Doe",
            label="Mayor",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Johnny",
            label="Council",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="John Doe",
            label="Deputy",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
    ]

    updated_people = group_people_by_name(
        known_mappings, people_by_name, people_to_link
    )
    assert len(updated_people["John Doe"]) == 3


def test_group_people_by_name_empty_inputs():
    """Test with empty inputs"""
    known_mappings = {}
    people_by_name = {}
    people_to_link = []

    updated_people = group_people_by_name(
        known_mappings, people_by_name, people_to_link
    )

    assert updated_people == {}


def test_group_people_by_name_complex_scenario():
    """Test complex scenario with multiple name variations and mappings"""
    known_mappings = {"John Smith": ["J. Smith"]}
    people_by_name = {
        "Jane Doe": [
            PersonSourceRecord(
                name="Jane Doe",
                label="Existing",
                phone_number=None,
                email=None,
                website=None,
                start_date=None,
                end_date=None,
                source_url="test",
            )
        ]
    }
    people_to_link = [
        PersonSourceRecord(
            name="John Smith",
            label="Mayor",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="J. Smith",
            label="Council",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            label="Deputy",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Bob Johnson",
            label="Clerk",
            phone_number=None,
            email=None,
            website=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
    ]

    updated_people = group_people_by_name(
        known_mappings, people_by_name, people_to_link
    )

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
    assert to_field_set_from_record(r3, ["emails"]) == {
        "c@example.com",
        "d@example.com",
    }

    # Both 'email' and 'emails'
    r4 = Dummy()
    r4.email = "e@example.com"
    r4.emails = ["f@example.com"]
    assert to_field_set_from_record(r4, ["email", "emails"]) == {
        "e@example.com",
        "f@example.com",
    }

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
    assert to_field_set_from_record(r3, ["urls"]) == {
        "http://example.net",
        "http://example.edu",
    }

    # Both 'url' and 'urls'
    r4 = Dummy()
    r4.url = "http://example.gov"
    r4.urls = ["http://example.info"]
    assert to_field_set_from_record(r4, ["url", "urls"]) == {
        "http://example.gov",
        "http://example.info",
    }

    # Neither present
    r5 = Dummy()
    assert to_field_set_from_record(r5, ["url", "urls"]) == set()


def test_is_weakly_tied_llm_person():
    class Dummy:
        pass

    person1 = Dummy()
    person1.name = "John Doe"
    person1.label = "Mayor"
    person1.email = ["john@example.com"]

    person2 = Dummy()
    person2.name = "Johnathan Doe"
    person2.label = "Mayor"
    person2.email = ["john@example.com"]

    assert is_weakly_tied({}, person1, person2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_person():
    class Dummy:
        pass

    person1 = Dummy()
    person1.name = "Jane Smith"
    person1.label = "Council Seat 2"
    person1.emails = ["jane@example.com"]

    person2 = Dummy()
    person2.name = "Janet Smith"
    person2.label = "Council Seat 2"
    person2.emails = ["jane@example.com"]
    assert is_weakly_tied({}, person1, person2, _TAXONOMY, MagicMock())


def test_is_not_weakly_tied_different_roles_and_emails():
    class Dummy:
        pass

    person1 = Dummy()
    person1.name = "Alice Johnson"
    person1.label = "Mayor"
    person1.emails = ["alice@example.com"]

    person2 = Dummy()
    person2.name = "Bob Johnson"
    person2.label = "Council"
    person2.emails = ["bob@example.com"]
    assert not is_weakly_tied({}, person1, person2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_same_identity():
    """Test is_weakly_tied when both records have the same identity."""
    identity_names = {"John Doe": ["John Doe", "Johnny", "J. Doe"]}
    record1 = PersonSourceRecord(
        name="Johnny",
        label="",
        email=None,
        url=None,
        source_url="test",
    )
    record2 = PersonSourceRecord(
        name="J. Doe",
        label="",
        email=None,
        url=None,
        source_url="test",
    )
    assert is_weakly_tied(identity_names, record1, record2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_different_identity():
    """Test is_weakly_tied when both records have different identities."""
    identity_names = {"John Doe": ["Johnny"], "Jane Smith": ["J. Smith"]}
    record1 = PersonSourceRecord(
        name="Johnny",
        label="",
        email=None,
        url=None,
        source_url="test",
    )
    record2 = PersonSourceRecord(
        name="J. Smith",
        label="",
        email=None,
        url=None,
        source_url="test",
    )
    assert not is_weakly_tied(identity_names, record1, record2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_name_overlap():
    """Test is_weakly_tied when names overlap."""
    identity_names = {}
    record1 = PersonSourceRecord(
        name="John Doe",
        label="",
        email=None,
        url=None,
        source_url="test",
    )
    record2 = PersonSourceRecord(
        name="Jon Doe",
        label="",
        email=None,
        url=None,
        source_url="test",
    )
    assert not is_weakly_tied(identity_names, record1, record2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_matching_designations():
    """Test is_weakly_tied when designations match."""
    identity_names = {}
    record1 = PersonSourceRecord(
        name="John Doe",
        label="Mayor",
        email=None,
        url=None,
        source_url="test",
    )
    record2 = PersonSourceRecord(
        name="Jon Doe",
        label="Mayor",
        email=None,
        url=None,
        source_url="test",
    )
    assert is_weakly_tied(identity_names, record1, record2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_email_overlap():
    """Test is_weakly_tied when emails overlap."""
    identity_names = {}
    record1 = PersonSourceRecord(
        name="John Doe",
        label="",
        email="john@example.com",
        url=None,
        source_url="test",
    )
    record2 = PersonSourceRecord(
        name="Jon Doe",
        label="",
        email="john@example.com",
        url=None,
        source_url="test",
    )
    assert is_weakly_tied(identity_names, record1, record2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_url_overlap():
    """Test is_weakly_tied when URLs overlap."""
    record1 = PersonSourceRecord(
        name="Abigail Doe",
        label="",
        email=None,
        url="http://example.com",
        source_url="test",
    )
    record2 = PersonSourceRecord(
        name="Abby Doe",
        label="",
        email=None,
        url="http://example.com",
        source_url="test",
    )
    assert not is_weakly_tied({}, record1, record2, _TAXONOMY, MagicMock())


def test_is_weakly_tied_no_overlap():
    """Test is_weakly_tied when there is no overlap."""
    identity_names = {}
    record1 = PersonSourceRecord(
        name="John Doe",
        label="Mayor",
        email=None,
        url="http://example.com",
        source_url="test",
    )
    record2 = PersonSourceRecord(
        name="Jane Smith",
        label="Council",
        email=None,
        url="http://example.org",
        source_url="test",
    )
    assert not is_weakly_tied(identity_names, record1, record2, _TAXONOMY, MagicMock())


def test_find_indexed_name_with_known_mapping():
    """Test when the name is found in known mappings."""
    known_mappings = {
        "John Smith": ["Jon Smith", "Jonathan Smith"],
        "Jane Doe": ["Janet Doe"],
    }
    people_by_name = {}

    assert (
        find_indexed_name("Jon Smith", people_by_name, known_mappings) == "John Smith"
    )
    assert find_indexed_name("Janet Doe", people_by_name, known_mappings) == "Jane Doe"
    assert (
        find_indexed_name("Unknown Name", people_by_name, known_mappings)
        == "Unknown Name"
    )


def test_find_indexed_name_with_similarity_matching():
    """Test when the name is matched based on similarity."""
    known_mappings = {}
    people_by_name = {"John Smith": [], "Jane Doe": [], "Alice Johnson": []}

    assert (
        find_indexed_name("Jon Smith", people_by_name, known_mappings) == "John Smith"
    )
    assert find_indexed_name("Janey Doe", people_by_name, known_mappings) == "Jane Doe"
    assert (
        find_indexed_name("Alicia Johnson", people_by_name, known_mappings)
        == "Alice Johnson"
    )


def test_find_indexed_name_with_last_name_containment():
    """Test when the last name contains or is contained by another."""
    known_mappings = {}
    people_by_name = {"John Smith": [], "Jane Doe": [], "Alice Johnson": []}

    assert (
        find_indexed_name("John Smithson", people_by_name, known_mappings)
        == "John Smith"
    )
    assert (
        find_indexed_name("Jane y. Doe", people_by_name, known_mappings) == "Jane Doe"
    )


def test_find_indexed_name_no_match():
    """Test when no match is found."""
    known_mappings = {}
    people_by_name = {"John Smith": [], "Jane Doe": [], "Alice Johnson": []}

    assert (
        find_indexed_name("Unknown Name", people_by_name, known_mappings)
        == "Unknown Name"
    )


def test_find_indexed_name_with_empty_people_by_name():
    """Test when people_by_name is empty."""
    known_mappings = {}
    people_by_name = {}

    assert (
        find_indexed_name("John Smith", people_by_name, known_mappings) == "John Smith"
    )


def test_find_indexed_name_with_empty_known_mappings():
    """Test when known_mappings is empty."""
    known_mappings = {}
    people_by_name = {"John Smith": [], "Jane Doe": [], "Alice Johnson": []}

    assert (
        find_indexed_name("John Smith", people_by_name, known_mappings) == "John Smith"
    )
    assert (
        find_indexed_name("Unknown Name", people_by_name, known_mappings)
        == "Unknown Name"
    )


@pytest.mark.parametrize(
    "name1, name2, expected",
    [
        ("John", "John", True),
        ("Jon", "John", True),
        ("Jonny", "John", True),
        ("john", "John", True),
        ("Danny", "Daniel", True),
        ("Dan", "Daniel", True),
        ("Dan", "Don", True),
        ("Sam", "Samuel", True),
        ("Chris", "Krist", True),
        ("", "", True),
        ("", "A", True),
        ("A", "", True),
        ("A", "B", True),
    ],
)
def test_are_names_similar_matrix(name1, name2, expected):
    assert are_names_similar(name1, name2) is expected


@pytest.mark.parametrize(
    "name1, name2, expected",
    [
        ("John Smith", "John Smith", True),  # exact match
        ("Jon Smith", "John Smith", True),  # similar first, exact last
        ("John Smith", "Smith John", False),  # reversed order, same names
        ("Johnny Smith", "John Smith", True),  # similar first, exact last
        ("John Smithson", "John Smith", True),  # last name containment
        ("John Smith", "John Smithson", True),  # last name containment
        (
            "Jane Smith",
            "John Smith",
            True,
        ),  # different first, same last - unfortunately
        ("John Doe", "Jane Doe", True),  # different first, same last - unfortunately
        ("John Smith", "John Doe", False),  # same first, different last
        ("Jon Smythe", "John Smith", False),  # similar first, different last
        ("J. Smith", "John Smith", True),  # initial, same last
        ("J. Smithson", "John Smith", True),  # initial, last name containment
        ("", "", False),  # empty names
        ("John", "John", False),  # missing last name
        ("Smith", "Smith", False),  # missing first name
        ("John Smith", "Smith", False),  # missing first in one
        ("John", "John Smith", False),  # missing last in one
    ],
)
def test_has_name_overlap_matrix(name1, name2, expected):
    assert has_name_overlap(name1, name2) is expected
