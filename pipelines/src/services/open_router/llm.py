import asyncio
import time
import json
import requests
from utils.request_utils import with_retry
from utils.log_utils import get_pipeline_run_logger
from utils import cost_utils
from pipelines_environment import get_env_vars

MAX_RETRIES = 5
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
# Conservative limit: DeepSeek V3/V3.2 context is 128k–164k tokens.
# We cap at 120k to leave headroom for the system prompt and response.
_MAX_INPUT_TOKENS = 120_000
_CHARS_PER_TOKEN = 4
_SEMAPHORE_CACHE: dict = {}

def _get_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if loop_id not in _SEMAPHORE_CACHE:
        _SEMAPHORE_CACHE[loop_id] = asyncio.Semaphore(20)
    return _SEMAPHORE_CACHE[loop_id]

MODELS_BY_TYPE = {
    "CHEAP": {},
    "STANDARD": {
        "model": "deepseek/deepseek-v3.2",
        "input_cost": 0.26 / 1000000,
        "output_cost": 0.38 / 1000000,
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
        seed=None):
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
            data=json.dumps({
                "model": model,
                "messages": messages,
                "temperature": 0.2,
                "top_p": 1.0,
                "response_format": response_format,
                **({"seed": seed} if seed is not None else {}),
                "provider": {
                    "order": provider_order or ["AtlasCloud", "SiliconFlow", "Google"],
                    "allow_fallbacks": False,
                    "data_collection": "deny",
                },
            }),
        )
        if not resp.ok:
            logger.error(f"OpenRouter error {resp.status_code} for model={model} provider_order={provider_order}: {resp.text}")
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
            raise ValueError(f"OpenRouter response missing 'choices'. Full body: {body}")
        response_text = choices[0]["message"]["content"]
        logger.debug(f"OpenRouter raw response: {response_text}")
        response = response_schema.model_validate_json(response_text) if response_schema else json.loads(response_text)

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
    result = await with_retry(logger, MAX_RETRIES, execute_async)
    end_time = time.time()
    logger.info(f"open_router LLM call took {end_time - start_time:.2f} seconds")
    return result
