import pytest
from runners.people_collector.schemas import PersonRecord
from runners.people_collector.steps.step_05_merge_records_within_llm.field_mergers import (
    merge_field,
    merge_labels,
)

pytestmark = pytest.mark.unit


def make_llm_person(name, label="", phone=None, email=None, website=None):
    """Helper function to create PersonRecord objects for testing"""
    return PersonRecord(
        name=name,
        other_names=[],
        label=label,
        phone={"data": phone} if phone else None,
        email={"data": email} if email else None,
        url={"data": website} if website else None,
        start_date=None,
        end_date=None,
        source_url="",
    )


def test_merge_field():
    """Test merging single value fields"""
    result = merge_field(["555-1234", "555-1234"])
    assert result == "555-1234"


def test_merge_labels():
    """One label per record, so merging is deduplication across the group."""
    p1 = make_llm_person("Sam", label="Council Member - Ward 1")
    p2 = make_llm_person("Sam", label="Mayor")
    p3 = make_llm_person("Sam", label="Council Member - Ward 1")
    result = merge_labels([p1, p2, p3])
    assert set(result) == {"Council Member - Ward 1", "Mayor"}


def test_merge_labels_skips_empty():
    p1 = make_llm_person("Dana", label="")
    p2 = make_llm_person("Dana", label="Ward 2")
    assert merge_labels([p1, p2]) == ["Ward 2"]
