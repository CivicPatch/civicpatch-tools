import os
import json
import requests
from utils.request_utils import with_retry
from utils.log_utils import log_llm_cost 
from utils.data_utils import MunicipalityContext

BASE_URI = "https://generativelanguage.googleapis.com/v1beta/models"
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite-preview-06-17"
]
# gemini-2.5-flash
# gemini-2.5-flash-preview-05-20
# gemini-2.5-flash-preview-04-17 broken as of 06/10
# Note: CANNOT get flash-lite to extract dates
DEFAULT_TIMEOUT = 180
MAX_RETRIES = 5

def run_prompt(municipality_context: MunicipalityContext, prompt, with_search=False, response_schema=None):
    """
    Run the prompt with model fallback and retry logic.
    """
    def execute_request(model):
        return make_request(model, prompt, municipality_context, with_search, response_schema)

    return with_retry(MAX_RETRIES, lambda: fallback_models(execute_request))

def make_request(model, prompt, municipality_context, with_search=False, response_schema=None):
    """
    Make an HTTP request to the Google Gemini API.
    """
    api_key = os.getenv("GOOGLE_GEMINI_TOKEN")
    if not api_key:
        raise ValueError("GOOGLE_GEMINI_TOKEN is not set in environment variables.")

    url = f"{BASE_URI}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": None if with_search else "application/json",
            "responseSchema": None if with_search else response_schema
        },
        "tools": {"googleSearch": {}} if with_search else None
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    if response.status_code == 200:
        log_usage(response.json(), model, municipality_context, with_search)
        return parse_response(response.json())
    else:
        log_error(response)
        return None

def fallback_models(execute_request):
    """
    Try all models in the MODELS list until one succeeds.
    """
    for model in MODELS:
        response = execute_request(model)
        if response:
            return response
    return None

def log_usage(response, model, municipality_context, with_search):
    """
    Log token usage for cost tracking.
    """
    usage = response.get("usageMetadata", {})
    prompt_tokens = usage.get("promptTokenCount", 0)
    completion_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
    log_llm_cost(municipality_context, "google_gemini", model, prompt_tokens, completion_tokens, with_search=with_search)

def log_error(response):
    """
    Log errors from the API response.

    Args:
        response: The API response.
    """
    print(f"Request failed. HTTP Status: {response.status_code}\nResponse: {response.text}")

def parse_response(response):
    """
    Parse the JSON response from the API.

    Args:
        response: The API response.

    Returns:
        Parsed JSON content or None if parsing fails.
    """
    try:
        response_text = response["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(response_text.replace("```json", "").replace("```", ""))
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Failed to parse JSON response: {e}")
        return None