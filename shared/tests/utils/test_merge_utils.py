from shared.schemas import PersonSourceRecord
from shared.utils.merge_utils import group_people_by_name, normalize_name


def test_normalize_name():
    assert normalize_name("John Doe") == "John Doe"
    assert normalize_name("  Jane Smith  ") == "Jane Smith"


def test_group_people_by_name_basic():
    """Test basic grouping of people with no existing mappings"""
    known_mappings = {}
    people_by_name = {}
    people_to_link = [
        PersonSourceRecord(
            name="John Doe",
            label="Mayor",
            phone=None,
            email=None,
            url=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Smith",
            label="Council",
            phone=None,
            email=None,
            url=None,
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
            phone=None,
            email=None,
            url=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Johnny",
            label="Council",
            phone=None,
            email=None,
            url=None,
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
                phone=None,
                email=None,
                url=None,
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
            phone=None,
            email=None,
            url=None,
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
                phone=None,
                email=None,
                url=None,
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
            phone=None,
            email=None,
            url=None,
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
            phone=None,
            email=None,
            url=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Johnny",
            label="Council",
            phone=None,
            email=None,
            url=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="John Doe",
            label="Deputy",
            phone=None,
            email=None,
            url=None,
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
                phone=None,
                email=None,
                url=None,
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
            phone=None,
            email=None,
            url=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="J. Smith",
            label="Council",
            phone=None,
            email=None,
            url=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Jane Doe",
            label="Deputy",
            phone=None,
            email=None,
            url=None,
            start_date=None,
            end_date=None,
            source_url="test",
        ),
        PersonSourceRecord(
            name="Bob Johnson",
            label="Clerk",
            phone=None,
            email=None,
            url=None,
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
