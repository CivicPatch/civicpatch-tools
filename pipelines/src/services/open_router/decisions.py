"""OpenRouter's Decisions endpoint: a small model given some state and a choice question answers
one label with a confidence, for a tiny fraction of a chat call's price."""

import time
from decimal import Decimal
from typing import Any, Dict

import httpx
from pipelines_environment import get_env_vars
from pydantic import BaseModel
from shared.schemas import LLMCall
from utils import cost_utils
from utils.log_utils import get_pipeline_run_logger
from utils.request_utils import with_retry

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "typesafe/jev-1.13"
GATEWAY = "openrouter"
QUESTION = "question"
CHOICE_TYPE = "choice"
_REQUEST_TIMEOUT_SECONDS = 60


class ChoiceAnswer(BaseModel):
    choice: str | None = None
    confidence: float | None = None


async def choose(
    pipeline_run_id: str,
    jurisdiction_ocdid: str,
    prompt_name: str,
    source_url: str,
    state: Dict[str, Any],
    instructions: str,
    criteria: Dict[str, str],
) -> ChoiceAnswer:
    """`state` is free-form by the endpoint's design: whatever the question is about, as JSON."""
    api_key = get_env_vars().get("OPEN_ROUTER_TOKEN")
    if not api_key:
        raise ValueError("OPEN_ROUTER_TOKEN is not set")
    logger = get_pipeline_run_logger(jurisdiction_ocdid)
    payload = {
        "model": JEV_MODEL,
        "state": state,
        "questions": {QUESTION: {"type": CHOICE_TYPE, "instructions": instructions, "criteria": criteria}},
    }

    async def execute() -> ChoiceAnswer:
        started = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DECISIONS_URL, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=_REQUEST_TIMEOUT_SECONDS
            )
        response.raise_for_status()
        body = response.json()
        usage = body.get("usage") or {}
        stated_cost = usage.get("cost")
        cost_utils.record_call(
            logger,
            pipeline_run_id,
            LLMCall(
                prompt_name=prompt_name,
                source_url=source_url,
                gateway=GATEWAY,
                model=JEV_MODEL,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                cost_usd=Decimal(str(stated_cost)) if stated_cost is not None else None,
                duration_ms=int((time.time() - started) * 1000),
            ),
        )
        return ChoiceAnswer.model_validate(body["answers"][QUESTION])

    return await with_retry(logger, execute)
