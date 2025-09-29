import os
import time
import instructor
import requests
import json
# from google import Gemini
from utils.request_utils import with_retry
from utils.log_utils import log_llm_cost

BASE_URI = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TIMEOUT = 180  # seconds
# Model fallback order: try flash-latest, then pro-latest
MODEL_FALLBACKS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview",
    "gemini-2.5-flash-lite",
]
# gemini-2.5-flash
# gemini-2.5-flash-preview-05-20
# gemini-2.5-flash-preview-04-17 broken as of 06/10
# Note: CANNOT get flash-lite to extract dates
MAX_RETRIES = 5

def run_prompt(jurisdiction_id: str, prompt, response_schema=None, content="", with_search=False):
    """
    Run a prompt against Google Gemini's API
    """
    print("gemini prompt: ", prompt)
    api_key = os.getenv("GOOGLE_GEMINI_TOKEN")
    if not api_key:
        raise ValueError("GOOGLE_GEMINI_TOKEN is not set in environment variables.")

    def execute(model):
        if with_search:
            response, input_tokens_num, output_tokens_num = make_request_with_search(model, api_key, prompt)
        else:
            client = instructor.from_provider(model=f"google/{model}", api_key=api_key)
            
            # Set up messages
            messages = [
                {"role": "system", "content": prompt}
            ]
            if content:
                messages.append({"role": "user", "content": content})

            response, completion = client.chat.completions.create_with_completion(
                response_model=response_schema,
                messages=messages
            )
            
            usage = completion.usage_metadata
            input_tokens_num = usage.prompt_token_count
            output_tokens_num = usage.candidates_token_count

        log_llm_cost(jurisdiction_id, "google_gemini", model, input_tokens_num, output_tokens_num, with_search=False)

        return response

    for model in MODEL_FALLBACKS:
        try:
            start_time = time.time()
            result = with_retry(MAX_RETRIES, lambda: execute(model))
            end_time = time.time()
            print(f"gemini {model} LLM call took {end_time - start_time:.2f} seconds")
            return result   
        except Exception:
            continue

    raise RuntimeError("All Gemini model fallbacks failed.")

def make_request_with_search(model, api_key, prompt):
    print("making request with search")
    url = f"{BASE_URI}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
        },
        "tools": {"googleSearch": {}}
    }
    headers = {"Content-Type": "application/json"}

    raw_response = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    print("raw_response:", raw_response.text)

    response = parse_raw_response(raw_response.json())

    usage = response.get("usageMetadata", {})
    input_tokens_num = usage.get("promptTokenCount", 0)
    output_tokens_num = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)

    return response, input_tokens_num, output_tokens_num

def parse_raw_response(response):
    """
    Parse the JSON response from the API.

    Args:
        response: The API response.

    Returns:
        Parsed JSON content or None if parsing fails.
    """
    response_text = response["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(response_text.replace("```json", "").replace("```", ""))