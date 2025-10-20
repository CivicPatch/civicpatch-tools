import pytest
from services.google_gemini.llm import run_prompt
from unittest.mock import patch

@pytest.mark.integration
@patch("services.google_gemini.llm.get_pipeline_logger")
def test_run_prompt_with_search(
    _mock_get_pipeline_logger
):
    """
    Integration test for run_prompt with Google Gemini API.
    """
    # Define test parameters
    request_id = "test_request_id"
    jurisdiction_id = "test_jurisdiction_id"
    prompt = """What is the capital of France? Return this in json in the format of 
    {
        "answer": str 
    }
    """
    response_schema = None
    content = ""
    with_search = True

    # Call the function
    response = run_prompt(
        request_id, 
        jurisdiction_id, 
        prompt, 
        response_schema, 
        content, 
        with_search
    )

    # Assertions
    assert response is not None, "Response should not be None."
    assert isinstance(response, dict), "Response should be a dictionary."