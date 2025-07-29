import json
import pytest
from src.utils.municipalities import get_municipalities_to_scrape

@pytest.fixture
def mock_municipalities_file(tmp_path):
    """
    Creates a temporary municipalities.json file for testing.
    """
    state = "CA"
    data_source = tmp_path / "data_source" / state
    data_source.mkdir(parents=True)
    municipalities_file = data_source / "municipalities.json"
    municipalities_file.write_text(json.dumps({
        "municipalities": [
            {"geoid": "12345", "meta_sources": ["source1"], "website": "http://example.com"},
            {"geoid": "67890", "meta_sources": ["source1", "source2"], "website": "http://example2.com"},
            {"geoid": "54321", "meta_sources": ["source1", "source2", "source3"], "website": "http://example3.com"},
            {"geoid": "98765", "meta_sources": ["source1"], "website": None}
        ]
    }))
    return str(municipalities_file)

def test_get_municipalities_to_scrape(mock_municipalities_file, monkeypatch):
    """
    Tests the get_municipalities_to_scrape function.
    """
    # Mock the file path
    def mock_get_municipalities_file_path(state):
        return mock_municipalities_file

    monkeypatch.setattr(
        "src.utils.municipalities.get_municipalities_file_path",
        mock_get_municipalities_file_path
    )

    # Test the function
    geoids = get_municipalities_to_scrape("CA", 2)
    assert geoids == ["12345", "67890"]

    # Test with geoids_to_ignore
    geoids = get_municipalities_to_scrape("CA", 2, geoids_to_ignore=["12345"])
    assert geoids == ["67890"]

    # Test with num_to_scrape greater than available municipalities
    geoids = get_municipalities_to_scrape("CA", 10)
    assert geoids == ["12345", "67890"]

    # Test with no valid municipalities
    geoids = get_municipalities_to_scrape("CA", 2, geoids_to_ignore=["12345", "67890"])
    assert geoids == []