import pytest
import os
import tempfile
from unittest.mock import patch
from jobs.people_collector.steps.step_04_preprocess_page_content.preprocess_page_content import preprocess_page_content
from jobs.people_collector.steps.step_04_preprocess_page_content.clean_html import clean_html
from jobs.people_collector.schemas import (
    Link, LinkStatus, WorkflowStatus
)

pytestmark = pytest.mark.integration


class DummyLogger:
    def debug(self, *a): pass
    def info(self, *a): pass
    def warning(self, *a): pass
    def error(self, *a): pass


# TMM-style HTML: email link wraps an img, all nested inside divs — no text on the <a> itself.
OAK_LEAF_HTML = """
<div class="tmm_container">
  <div class="tmm_member">
    <div class="tmm_textblock">
      <div class="tmm_names"><span class="tmm_fname">Tom</span> <span class="tmm_lname">Leverentz</span></div>
      <div class="tmm_job">Mayor</div>
      <div class="tmm_scblock">
        <a class="tmm_sociallink" href="mailto:tleverentz@oakleaftexas.org" title="email">
          <img alt="email" src="https://example.org/email.png">
        </a>
      </div>
    </div>
  </div>
  <div class="tmm_member">
    <div class="tmm_textblock">
      <div class="tmm_names"><span class="tmm_fname">Mitchell</span> <span class="tmm_lname">Burnett</span></div>
      <div class="tmm_job">Place 1</div>
      <div class="tmm_scblock">
        <a class="tmm_sociallink" href="mailto:mburnett@oakleaftexas.org" title="email">
          <img alt="email" src="https://example.org/email.png">
        </a>
      </div>
    </div>
  </div>
</div>
"""


def test_clean_html_preserves_mailto_links():
    result = clean_html(DummyLogger(), OAK_LEAF_HTML)
    assert "mailto:tleverentz@oakleaftexas.org" in result
    assert "mailto:mburnett@oakleaftexas.org" in result


def test_clean_html_preserves_mailto_links_after_div_unwrap():
    """Divs are stripped by clean_html — the <a> tags must survive."""
    result = clean_html(DummyLogger(), OAK_LEAF_HTML)
    assert "<a" in result
    assert 'href="mailto:' in result

@pytest.fixture
def mock_context():
    return {
        "state": "test_state",
        "geoid": "12345",
        "links": [
            {"url": "http://example.com/page1", "folder_name": "page1", "status": LinkStatus.SCRAPED.value},
            {"url": "http://example.com/page2", "folder_name": "page2", "status": LinkStatus.SCRAPED.value},
        ],
        "steps": {
            WorkflowStatus.PREPROCESS_PAGE_CONTENT.value: {
                "elapsed_times": [],
                "total_elapsed_time_seconds": 0,
            }
        }
    }

@pytest.fixture
def mock_page_to_preprocess():
    return {"url": "http://example.com/page1", "folder_name": "page1"}

@pytest.fixture
def fixtures_directory():
    # Resolve the absolute path for the fixtures directory
    relative_path = os.path.join(os.path.dirname(__file__), "../../fixtures")
    absolute_path = os.path.abspath(relative_path)
    return absolute_path

@pytest.fixture
def temp_cache_path():
    # Create a temporary directory for the cache path
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@patch("utils.data_path_utils.get_cache_path")
def test_preprocess_page_content_divisions(mock_get_cache_path, mock_context, mock_page_to_preprocess, fixtures_directory, temp_cache_path):
    # Mock the cache path to point to the temporary directory
    mock_get_cache_path.return_value = temp_cache_path

    # Copy the input HTML file to the temporary cache path
    input_html_file = os.path.join(fixtures_directory, "sample_divisions.html")
    print("Input HTML File Path:", input_html_file)  # Debugging output
    output_html_file_path = os.path.join(temp_cache_path, "page1", "original.html")
    os.makedirs(os.path.dirname(output_html_file_path), exist_ok=True)
    with open(input_html_file, "r", encoding="utf-8") as f_in, open(output_html_file_path, "w", encoding="utf-8") as f_out:
        f_out.write(f_in.read())

    # Run the preprocess_page_content function
    result = preprocess_page_content(mock_context, mock_page_to_preprocess)

    # Verify the generated files
    original_md_path = os.path.join(temp_cache_path, "page1", "original.md")
    preprocessed_md_path = os.path.join(temp_cache_path, "page1", "preprocessed.md")

    assert os.path.exists(original_md_path), "Original markdown file was not created."
    assert os.path.exists(preprocessed_md_path), "Preprocessed markdown file was not created."

    with open(original_md_path, "r", encoding="utf-8") as f:
        original_md_content = f.read()
    with open(preprocessed_md_path, "r", encoding="utf-8") as f:
        preprocessed_md_content = f.read()

    # Verify the content of the generated files
    assert "Ward 5" in original_md_content
    assert "At-large" in preprocessed_md_content

    # Verify the link status is updated
    updated_links = result["links"]
    assert any(link["status"] == LinkStatus.PREPROCESSED.value for link in updated_links)