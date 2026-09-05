"""Gemini with Google Search grounding — the one thing OpenRouter cannot route.

No Gemini model on OpenRouter supports native web search (probed 2026-09-03: all 7 endpoints
fail its "Filter by Native Web Search Support"), and Exa is a different search engine. So these
calls stay on Google's REST API while everything else goes through `services/open_router`.
"""

import json
import time

import requests
from pipelines_environment import get_env_vars
from utils import cost_utils
from utils.log_utils import get_pipeline_run_logger
from utils.request_utils import with_retry

BASE_URI = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TIMEOUT = 180  # seconds
# Model fallback order: try flash-latest, then pro-latest
MODEL_FALLBACKS = [
    "gemini-2.5-flash",
    # "gemini-2.5-flash-preview-09-2025",
    # "gemini-2.5-flash-lite",
]
FIND_JURISDICTION_URL_MODEL_FALLBACKS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
]
# gemini-2.5-flash
# gemini-2.5-flash-preview-05-20
# gemini-2.5-flash-preview-04-17 broken as of 06/10
# Note: CANNOT get flash-lite to extract dates


async def run_prompt(pipeline_run_id, jurisdiction_ocdid, prompt, model_fallbacks=None):
    """Ask Gemini a grounded question. Returns parsed JSON, not a validated model.

    Tool calls and structured output do not work together on gemini-2.5, which both ladders end
    on, so the answer comes back as fenced free text and `parse_raw_response` reads it.
    """
    logger = get_pipeline_run_logger(jurisdiction_ocdid)
    logger.info("Running Gemini prompt")
    logger.debug(f"Prompt: \n{prompt}")
    api_key = get_env_vars().get("GOOGLE_GEMINI_TOKEN")
    if not api_key:
        raise ValueError("GOOGLE_GEMINI_TOKEN is not set in environment variables.")

    def execute(model):
        response, input_tokens_num, output_tokens_num = make_request_with_search(
            logger, model, api_key, prompt
        )
        cost_utils.add_llm_cost(
            logger,
            pipeline_run_id,
            jurisdiction_ocdid,
            "google_gemini",
            model,
            input_tokens_num,
            output_tokens_num,
            with_search=True,
        )
        return response

    for model in model_fallbacks or MODEL_FALLBACKS:
        try:
            start_time = time.time()
            result = await with_retry(logger, lambda: execute(model))
            end_time = time.time()
            logger.info(
                f"gemini {model} LLM call took {end_time - start_time:.2f} seconds"
            )
            return result
        except Exception as e:
            # Logged, not swallowed: a bad key and a bad model look identical otherwise.
            logger.warning(f"gemini {model} failed, trying the next fallback: {e}")

    raise RuntimeError("All Gemini model fallbacks failed.")


def make_request_with_search(logger, model, api_key, prompt):
    url = f"{BASE_URI}/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
        },
        "tools": [{"googleSearch": {}}],
    }
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    raw_response = requests.post(
        url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT
    )
    response_json = raw_response.json()

    response = parse_raw_response(response_json)
    logger.debug(f"Gemini raw response: {response}")

    usage = response_json.get("usageMetadata", {})
    input_tokens_num = usage.get("promptTokenCount", 0)
    output_tokens_num = usage.get("candidatesTokenCount", 0) + usage.get(
        "thoughtsTokenCount", 0
    )

    return response, input_tokens_num, output_tokens_num


def parse_raw_response(response):
    candidates = response.get("candidates")
    if not candidates:
        block_reason = response.get("promptFeedback", {}).get("blockReason", "unknown")
        raise ValueError(
            f"Gemini returned no candidates. Block reason: {block_reason}. Full response: {response}"
        )
    response_text = candidates[0]["content"]["parts"][0]["text"]
    return json.loads(response_text.replace("```json", "").replace("```", ""))
