import pytest
from steps.step_01_scraping.scraper import get_website_content

@pytest.mark.flaky(reruns=3)
def test_get_website_content():
    """
    Integration test for get_website_content.
    Fetches content from a real website and verifies the response.
    """
    # Use a publicly available test website
    test_url = "https://example.com"
    
    # Call the function
    content = get_website_content(test_url)
    
    # Assert that the content is not empty
    assert content is not None
    assert "<html" in content.lower()  # Check if HTML content is returned
    assert "example domain" in content.lower()  # Verify specific content in the page