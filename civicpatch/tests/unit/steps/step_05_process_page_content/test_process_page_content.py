import os
from unittest.mock import patch
from schemas import LLMPerson, LinkStatus, PipelineStatus, ProcessPageContentStep
from steps.step_05_process_page_content.process_page_content import process_page_content
from utils.url_utils import format_url_to_folder

def make_llm_person(name, roles=None, phone=None, email=None, website=None):
    """
    Helper function to create an LLMPerson object for testing.
    """
    return LLMPerson(
        name=name,
        roles=[{"data": r} for r in (roles or [])],
        divisions=[],
        phone_number={"data": phone} if phone else None,
        email={"data": email} if email else None,
        website={"data": website} if website else None,
        start_date=None,
        end_date=None
    )

@patch("utils.data_path_utils.get_cache_path")
@patch("utils.data_utils.get_municipality_context")
@patch("services.google_gemini.llm.run_prompt")
@patch("services.openai.llm.run_prompt")
def test_process_page_content_basic(
    mock_openai_run_prompt,
    mock_google_gemini_run_prompt,
    mock_get_municipality_context,
    mock_get_cache_path
):
    # Mock `get_cache_path`
    mock_cache_path = "/mock/cache/path"
    mock_get_cache_path.return_value = mock_cache_path

    # Create the mocked file structure
    os.makedirs(os.path.join(mock_cache_path, "example_com"), exist_ok=True)
    preprocessed_file_path = os.path.join(mock_cache_path, "example_com", "preprocessed.md")
    with open(preprocessed_file_path, "w", encoding="utf-8") as f:
        f.write("# Sample Preprocessed Content\nThis is a test file for preprocessed content.")

    # Mock `get_municipality_context`
    mock_get_municipality_context.return_value = {
        "state": "wa",
        "geoid": "5367000",
        "municipality_entry": {
            "name": "Spokane",
            "geoid": "5367000",
            "website": "https://spokanecity.org",
            "counties": ["Spokane County"],
            "type": "city",
            "government_type": "mayor_council"
        }
    }

    # Mock LLM responses
    mock_google_gemini_run_prompt.return_value = {
        "people": [
            {
                "name": "Alice Johnson",
                "roles": [{"data": "council member"}],
                "divisions": [],
                "phone_number": {"data": "123"},
                "email": None,
                "website": None,
                "start_date": None,
                "end_date": None
            }
        ],
        "thought": "Identified Alice Johnson as a council member based on the content."
    }
    mock_openai_run_prompt.return_value = {
        "people": [
            {
                "name": "Bob Smith",
                "roles": [{"data": "mayor"}],
                "divisions": [],
                "phone_number": {"data": "456"},
                "email": None,
                "website": None,
                "start_date": None,
                "end_date": None
            }
        ],
        "thought": "Identified Bob Smith as the mayor based on the content."
    }

    # Mock context
    context = {
        "state": "wa",
        "geoid": "5367000",
        "progress": {"current_data": 0},
        "steps": {
            PipelineStatus.RESEARCH_MUNICIPALITY.value: {
                "government_type": "mayor_council",
                "elected_officials": [{"name": "Alice Johnson"}]
            },
            PipelineStatus.PROCESS_PAGE_CONTENT.value: ProcessPageContentStep(
                records_by_llm={
                    "google_gemini": {
                        "Alice Johnson": [
                            make_llm_person("Alice Johnson", roles=["council member"], phone="123")
                        ]
                    },
                    "openai": {
                        "Bob Smith": [
                            make_llm_person("Bob Smith", roles=["mayor"], phone="456")
                        ]
                    }
                }
            )
        },
        "links": [
            {"url": "https://example.com", "status": LinkStatus.PENDING.value, "folder_name": "example_com"}
        ],
        "names": {}
    }

    # Mock page_to_process
    page_to_process = {"url": "https://example.com", "folder_name": "example_com"}

    # Call the function and assign the result
    result = process_page_content(context, page_to_process)

    # Assertions
    assert result["progress"]["current_data"] == 1  # Ensure progress is updated correctly
    assert result["links"][0]["status"] == LinkStatus.DONE.value
    assert "Alice Johnson" in result["names"]
    assert "Bob Smith" in result["names"]

    # Cleanup mocked file structure
    os.remove(preprocessed_file_path)
    os.rmdir(os.path.join(mock_cache_path, "example_com"))

