import time
import requests
import json
from google import genai  # type: ignore[attr-defined]
from google.genai import types
from utils.request_utils import with_retry
from utils.log_utils import get_workflow_logger
from utils import cost_utils
from pipelines_environment import get_env_vars

BASE_URI = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TIMEOUT = 180  # seconds
# Model fallback order: try flash-latest, then pro-latest
MODEL_FALLBACKS = [
    "gemini-2.5-flash",
    # "gemini-2.5-flash-preview-09-2025",
    # "gemini-2.5-flash-lite",
]
# gemini-2.5-flash
# gemini-2.5-flash-preview-05-20
# gemini-2.5-flash-preview-04-17 broken as of 06/10
# Note: CANNOT get flash-lite to extract dates
MAX_RETRIES = 5

async def run_prompt(
        request_id,
        jurisdiction_ocdid: str,
        prompt,
        response_schema=None,
        content="",
        with_search=False
    ):
    logger = get_workflow_logger(jurisdiction_ocdid)
    logger.info(f"Running Gemini prompt")
    logger.debug(f"Prompt: \n{prompt}")
    api_key = get_env_vars().get("GOOGLE_GEMINI_TOKEN")
    if not api_key:
        raise ValueError("GOOGLE_GEMINI_TOKEN is not set in environment variables.")

    def execute(model):
        if with_search:
            response, input_tokens_num, output_tokens_num = make_request_with_search(logger, model, api_key, prompt)
        else:
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0,
                system_instruction=prompt,
            )
            completion = client.models.generate_content(
                model=model,
                contents=content or ".",
                config=config,
            )
            assert response_schema is not None
            response = response_schema.model_validate_json(completion.text)
            input_tokens_num = completion.usage_metadata.prompt_token_count
            output_tokens_num = completion.usage_metadata.candidates_token_count

        cost_utils.add_llm_cost(
            logger,
            request_id,
            jurisdiction_ocdid,
            "google_gemini",
            model,
            input_tokens_num,
            output_tokens_num,
            with_search=with_search
        )

        return response

    for model in MODEL_FALLBACKS:
        try:
            start_time = time.time()
            result = await with_retry(logger, MAX_RETRIES, lambda: execute(model))
            end_time = time.time()
            logger.info(f"gemini {model} LLM call took {end_time - start_time:.2f} seconds")
            return result
        except Exception:
            continue

    raise RuntimeError("All Gemini model fallbacks failed.")

def make_request_with_search(logger, model, api_key, prompt):
    url = f"{BASE_URI}/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
        },
        "tools": {"googleSearch": {}}
    }
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    raw_response = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    response_json = raw_response.json()

    response = parse_raw_response(response_json)
    logger.debug(f"Gemini raw response: {response}")

    usage = response_json.get("usageMetadata", {})
    input_tokens_num = usage.get("promptTokenCount", 0)
    output_tokens_num = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)

    return response, input_tokens_num, output_tokens_num

def parse_raw_response(response):
    candidates = response.get("candidates")
    if not candidates:
        block_reason = response.get("promptFeedback", {}).get("blockReason", "unknown")
        raise ValueError(f"Gemini returned no candidates. Block reason: {block_reason}. Full response: {response}")
    response_text = candidates[0]["content"]["parts"][0]["text"]
    return json.loads(response_text.replace("```json", "").replace("```", ""))
