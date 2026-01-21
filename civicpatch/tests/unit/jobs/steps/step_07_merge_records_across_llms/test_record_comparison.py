import datetime
import pytest

from domain.models import Person
from jobs.people_collector.schemas import FieldComparison
from jobs.people_collector.steps.step_07_merge_records_across_llms import record_comparison

pytestmark = pytest.mark.unit

def make_person(name=None, emails=None, roles=None):
    import datetime
    return Person(
        name=name,
        emails=emails if emails is not None else [],
        roles=roles if roles is not None else [],
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government",
        source_urls=["https://example.com"],
        updated_at=datetime.datetime.now().isoformat()
    )

def test_agreement_no_disagreement():
    merged = make_person(name="Alice", emails=["alice@example.com"], roles=["Manager"])
    grouped = {
        "llm1": [make_person(name="Alice", emails=["alice@example.com"], roles=["Manager"])],
        "llm2": [make_person(name="Alice", emails=["alice@example.com"], roles=["Manager"])]
    }
    fields = ["name", "emails", "roles"]
    field_weights = {"name": 1.0, "emails": 1.0, "roles": 1.0}
    result = record_comparison.collect_field_comparisons(merged, grouped, fields, field_weights)
    assert result == []

def test_disagreement_in_name():
    merged = make_person(name="Alice", emails=["alice@example.com"], roles=["Manager"])
    grouped = {
        "llm1": [make_person(name="Alice", emails=["alice@example.com"], roles=["Manager"])],
        "llm2": [make_person(name="Alicia", emails=["alice@example.com"], roles=["Manager"])]
    }
    fields = ["name", "emails", "roles"]
    field_weights = {"name": 1.0, "emails": 1.0, "roles": 1.0}
    result = record_comparison.collect_field_comparisons(merged, grouped, fields, field_weights)
    assert any(fc.field == "name" for fc in result)
    assert all(isinstance(fc, FieldComparison) for fc in result)

def test_missing_llm_value():
    merged = make_person(name="Bob", emails=["bob@example.com"], roles=["Staff"])
    grouped = {
        "llm1": [],
        "llm2": [make_person(name="Bob", emails=["bob@example.com"], roles=["Staff"])]
    }
    fields = ["name", "emails", "roles"]
    field_weights = {"name": 1.0, "emails": 1.0, "roles": 1.0}
    result = record_comparison.collect_field_comparisons(merged, grouped, fields, field_weights)
    assert result  # Should have disagreements due to missing llm1

def test_list_field_disagreement():
    merged = make_person(name="Carol", emails=["carol@example.com"], roles=["Director", "Manager"])
    grouped = {
        "llm1": [make_person(name="Carol", emails=["carol@example.com"], roles=["Director"])],
        "llm2": [make_person(name="Carol", emails=["carol@example.com"], roles=["Staff"])]
    }
    fields = ["roles"]
    field_weights = {"roles": 1.0}
    result = record_comparison.collect_field_comparisons(merged, grouped, fields, field_weights)
    assert any(fc.field == "roles" for fc in result)

def test_email_with_disagreement():
    merged = make_person(name="David", emails=["david@example.com"], roles=["Analyst"])
    grouped = {
        "llm1": [make_person(name="David", emails=["david@example.com"], roles=["Analyst"])],
        "llm2": [make_person(name="David", emails=["david.smith@example.com"], roles=["Analyst"])]
    }
    fields = ["emails"]
    field_weights = {"emails": 1.0}
    result = record_comparison.collect_field_comparisons(merged, grouped, fields, field_weights)
    print(result)
    # Should detect disagreement in emails
    assert any(fc.field == "emails" for fc in result)

def test_email_no_disagreement_with_mixed_cases():
    merged = make_person(name="Eve", emails=["eve@example.com"], roles=["Manager"])
    grouped = {
        "llm1": [make_person(name="Eve", emails=["eve@example.com"], roles=["Manager"])],
        "llm2": [make_person(name="Eve", emails=["EVE@example.com"], roles=["Manager"])]
    }
    fields = ["emails"]
    field_weights = {"emails": 1.0}
    result = record_comparison.collect_field_comparisons(merged, grouped, fields, field_weights)
    assert result == []  # No disagreement due to case insensitivity