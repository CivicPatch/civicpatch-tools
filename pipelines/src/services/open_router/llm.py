import asyncio
import json
import time

import requests
from pipelines_environment import get_env_vars
from utils import cost_utils
from utils.log_utils import get_pipeline_run_logger
from utils.request_utils import with_retry

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
# Conservative limit: DeepSeek V3/V3.2 context is 128k–164k tokens.
# We cap at 120k to leave headroom for the system prompt and response.
_MAX_INPUT_TOKENS = 120_000
_CHARS_PER_TOKEN = 4
# Bounds a degenerate repetition loop. Unset, the ceiling is the provider's
# max_completion_tokens (393,216 on v4-flash): one observed loop echoed an image URL's
# query string for 92,669 chars and took 734 SECONDS before failing JSON validation — then
# retried, 5 times over.
#
# Sized off real traffic, not the cap: the largest genuine response across 88 recorded
# runs is 3,314 chars (~828 tokens) and the median is 953 chars. 4,096 is ~5x the largest
# real answer while cutting that 734s runaway to roughly 130s.
# It does not make a looping call succeed — it makes it fail fast and cheap.
_MAX_OUTPUT_TOKENS = 4_096
# Scrapes keep 0.2. Extraction gains nothing from sampling diversity, but two things here
# depend on it: with_retry treats a malformed-JSON ValidationError as retryable, which only
# helps if the retry can draw a different sample, and greedy decoding is *more* prone to the
# degenerate repetition loop we already hit once. Evals pin this to 0 — same page, same
# answer — and production should only follow once that is measured, not assumed. Note 0
# does not buy determinism outright: v4-flash is MoE behind dynamic batching, so expert
# routing shifts with whatever else is in the batch.
_DEFAULT_TEMPERATURE = 0.2
_SEMAPHORE_CACHE: dict = {}


def max_content_chars(prompt: str) -> int:
    """Return how many content characters fit under the token limit for the given prompt."""
    prompt_tokens = len(prompt) // _CHARS_PER_TOKEN
    return (_MAX_INPUT_TOKENS - prompt_tokens) * _CHARS_PER_TOKEN


def _get_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if loop_id not in _SEMAPHORE_CACHE:
        _SEMAPHORE_CACHE[loop_id] = asyncio.Semaphore(20)
    return _SEMAPHORE_CACHE[loop_id]


MODELS_BY_TYPE = {
    "CHEAP": {},
    "STANDARD": {
        "model": "deepseek/deepseek-v4-flash",
        "input_cost": 0.14 / 1000000,
        "output_cost": 0.28 / 1000000,
    },
}


async def run_prompt(
    request_id,
    jurisdiction_ocdid: str,
    prompt,
    response_schema=None,
    content="",
    model_type="STANDARD",
    provider_order=None,
    allow_fallbacks=True,
    seed=None,
    temperature: float = _DEFAULT_TEMPERATURE,
):
    logger = get_pipeline_run_logger(jurisdiction_ocdid)
    logger.info("Running OpenRouter prompt")
    logger.debug(f"Prompt: \n{prompt}")

    estimated_tokens = (len(prompt) + len(content)) // _CHARS_PER_TOKEN
    if estimated_tokens > _MAX_INPUT_TOKENS:
        raise ValueError(
            f"Content too large for LLM: ~{estimated_tokens:,} estimated tokens "
            f"(limit: ~{_MAX_INPUT_TOKENS:,})"
        )

    api_key = get_env_vars().get("OPEN_ROUTER_TOKEN")
    if not api_key:
        raise ValueError("OPEN_ROUTER_TOKEN is not set")

    model_config = MODELS_BY_TYPE.get(model_type, MODELS_BY_TYPE["STANDARD"])
    model = model_config["model"]

    messages = [{"role": "system", "content": prompt}]
    if content:
        messages.append({"role": "user", "content": content})

    response_format = (
        {
            "type": "json_schema",
            "json_schema": {
                "name": response_schema.__name__,
                "strict": True,
                "schema": response_schema.model_json_schema(),
            },
        }
        if response_schema
        else {"type": "json_object"}
    )

    def execute():
        resp = requests.post(
            url=BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://civicpatch.org",
                "X-Title": "CivicPatch",
            },
            data=json.dumps(
                {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": 1.0,
                    "max_tokens": _MAX_OUTPUT_TOKENS,
                    "response_format": response_format,
                    **({"seed": seed} if seed is not None else {}),
                    "provider": {
                        # Every provider here must support `structured_outputs` — we send
                        # json_schema with strict=True, and allow_fallbacks is False, so a
                        # provider that only does `response_format` (json_object) makes
                        # OpenRouter return 404 "No endpoints found" rather than routing on.
                        # Google (no v4-flash endpoint) and SiliconFlow (no
                        # structured_outputs) were both dropped for that reason.
                        # DigitalOcean first, AtlasCloud as fallback. Measured 2026-08-15
                        # across three runs: roles 0.976-1.000 and district 1.000 for both,
                        # so they are equivalent on what the taxonomy model needs, and
                        # DigitalOcean is 2.7x cheaper ($0.0079 vs $0.0213 per eval run).
                        # AtlasCloud is materially better on contact fields (8 missing
                        # values vs 66), which is why it stays as the fallback.
                        #
                        # DeepInfra removed: 109 missing values and a flat 0.000 on both
                        # start_date and end_date across every run. allow_fallbacks is
                        # False, so anything left in this list is a provider we can land on
                        # — leaving it here meant production silently used it.
                        "order": provider_order or ["DigitalOcean", "AtlasCloud"],
                        "allow_fallbacks": False,
                        "data_collection": "deny",
                    },
                }
            ),
        )
        if not resp.ok:
            logger.error(
                f"OpenRouter error {resp.status_code} for model={model} provider_order={provider_order}: {resp.text}"
            )
        resp.raise_for_status()
        body = resp.json()

        routed_model = body.get("model", model)
        provider = body.get("provider", "unknown")
        logger.info(f"OpenRouter routed to: {routed_model} via {provider}")

        choices = body.get("choices")
        if not choices:
            logger.warning(
                f"OpenRouter response missing 'choices'. "
                f"Body: {body} | "
                f"Headers: {dict(resp.headers)}"
            )
            raise ValueError(
                f"OpenRouter response missing 'choices'. Full body: {body}"
            )
        response_text = choices[0]["message"]["content"]
        logger.debug(f"OpenRouter raw response: {response_text}")
        response = (
            response_schema.model_validate_json(response_text)
            if response_schema
            else json.loads(response_text)
        )

        usage = body.get("usage", {})
        cost_utils.add_llm_cost(
            logger,
            request_id,
            jurisdiction_ocdid,
            "open_router",
            model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            with_search=False,
            provider=provider,
            routed_model=routed_model,
        )

        return response

    loop = asyncio.get_running_loop()

    async def execute_async():
        async with _get_semaphore():
            return await loop.run_in_executor(None, execute)

    start_time = time.time()
    result = await with_retry(logger, execute_async)
    end_time = time.time()
    logger.info(f"open_router LLM call took {end_time - start_time:.2f} seconds")
    return result
