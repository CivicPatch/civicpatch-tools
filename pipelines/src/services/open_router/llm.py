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


# Only `model` is read. The per-token costs that used to sit here were never consulted —
# cost_utils owns pricing, keyed by (model, provider), because the price depends on which
# provider OpenRouter routes to and a single number here cannot express that.
#
# A "CHEAP" tier used to exist as an empty dict, which was worse than absent: model_type
# falls back to STANDARD only when the key is *missing*, so asking for CHEAP returned {}
# and raised KeyError on the next line.
MODELS_BY_TYPE = {
    "STANDARD": {"model": "deepseek/deepseek-v4-flash"},
}


def _require_every_property(schema):
    """Strict structured output requires every property to appear in `required`; pydantic
    omits any field carrying a default. Providers then skip those keys entirely — measured
    2026-08-16, that returned 0 of 35 emails across the eval corpus, and 6 of 6 once fixed.
    Nullability still comes from the field type, so this changes what is emitted, not what
    is allowed."""
    if isinstance(schema, dict):
        if schema.get("type") == "object" and "properties" in schema:
            schema["required"] = list(schema["properties"])
        for value in schema.values():
            _require_every_property(value)
    elif isinstance(schema, list):
        for item in schema:
            _require_every_property(item)
    return schema


async def run_prompt(
    request_id,
    jurisdiction_ocdid: str,
    prompt,
    response_schema=None,
    content="",
    model_type="STANDARD",
    provider_order=None,
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
                "schema": _require_every_property(response_schema.model_json_schema()),
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
                        # One order for every prompt — nothing passes provider_order in
                        # production, so this is the single routing decision.
                        #
                        # AtlasCloud leads on recall, which is what the pipeline is bounded
                        # by. Measured 2026-08-15: on relevant_page it returns every wanted
                        # link (recall 1.000, 1 failing case) against DigitalOcean's 0.875
                        # and 4 — and DigitalOcean returned *zero* links for one page. That
                        # step runs first and decides which pages the extractor ever sees,
                        # so a link it never returns is a page nothing downstream can
                        # recover. On officials it misses 6 values to DigitalOcean's 63.
                        #
                        # DigitalOcean is 2.7x cheaper and equivalent on roles and district
                        # (0.976-0.992 and 1.000 for both), which is why it led until
                        # relevant_page was measured. It stays as the fallback.
                        "order": provider_order or ["AtlasCloud", "DigitalOcean"],
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
