import pytest
from scripts.generate_data_comment import generate_data_comment
from domain.models import Official, Office

pytestmark = pytest.mark.unit

def test_generate_table_with_full_data():
    official = Official(
        name="Jane Doe",
        office=Office(name="Mayor", division_ocdid="ocd-division/country:us"),
        emails=["jane@example.com"],
        phones=["555-1234"],
        urls=["https://example.com"],
        start_date="2020-01-01",
        end_date="2024-01-01",
        image="https://example.com/jane.jpg",
        cdn_image="https://cdn.example.com/jane.jpg",
        jurisdiction_ocdid="ocd-division/country:us",
        source_urls=["https://source.com"],
        updated_at="2024-01-01"
    )
    table = generate_data_comment([official])
    assert "Jane Doe" in table
    assert "[Link](https://example.com)" in table
    assert "![image of Jane Doe](https://example.com/jane.jpg)" in table

def test_generate_table_with_missing_data():
    official = Official(
        name="John Smith",
        office=Office(name="", division_ocdid=None),
        emails=[],
        phones=[],
        urls=[],
        start_date=None,
        end_date=None,
        cdn_image=None,
        jurisdiction_ocdid="ocd-division/country:us",
        source_urls=[],
        updated_at="2024-01-01"
    )
    table = generate_data_comment([official])
    assert "John Smith" in table
    assert "N/A" in table