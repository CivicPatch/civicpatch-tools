import os
import json
from shared.utils import data_path_utils
from utils import log_utils
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel

_COSTS_BY_RUN = {}

def get_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')

class LLMCall(BaseModel):
    """One HTTP call to a gateway, named for the columns it lands in (`llm_calls`, migration
    171) so `costs.json` needs no translation on the way in."""

    @property
    def timestamp(self) -> str:
        return get_timestamp()

    # what was asked, and of what
    prompt_name: str
    source_url: str | None = None
    chunk_index: int | None = None
    chunk_count: int | None = None
    # The two retry loops mean different things: `attempt` is the transport retry inside one
    # call, `seed` marks the heuristics pass that re-ran the whole prompt.
    attempt: int = 1
    seed: int | None = None

    # who answered, and by what route
    gateway: str
    model: str
    routed_model: str = ""
    upstream_provider: str = ""
    generation_id: str | None = None

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0

    # What the provider says it charged. None when it states none — the grounded Google calls,
    # which are punted from `llm_calls` entirely. Never derived from a price table: one went
    # stale silently and reported zero spend for an unlisted (model, provider) pair.
    cost_usd: Decimal | None = None
    web_search: bool = False
    duration_ms: int | None = None

    finish_reason: str | None = None
    # Why the response could not be used; None means it was. The call billed either way.
    error: str | None = None


def reset_cost_tracker(pipeline_run_id: str):
    """Drop a run's accumulated costs.

    Only needed by callers that reuse one id across measurements — the evals do. A real
    scrape gets a fresh run id, so its tally starts empty without anyone remembering to ask.
    """
    _COSTS_BY_RUN.pop(pipeline_run_id, None)


def get_cost_tracker(pipeline_run_id: str):
    """Keyed on the run, not the jurisdiction.

    Keyed on the jurisdiction, two runs for the same place in one process shared a tally and
    the second inherited the first's — the eval provider comparison read input tokens as
    exactly double for byte-identical work. A run id makes that impossible rather than
    leaving a `reset_cost_tracker` call to remember.
    """
    if pipeline_run_id not in _COSTS_BY_RUN:
        _COSTS_BY_RUN[pipeline_run_id] = {
            'llm_costs': [],
        }
    return _COSTS_BY_RUN[pipeline_run_id]

def record_call(
    logger: log_utils.PipelineRunLogger, pipeline_run_id: str, call: LLMCall
) -> None:
    """Add one call to this run's tally. The model crosses the boundary, not fifteen arguments."""
    get_cost_tracker(pipeline_run_id)['llm_costs'].append(
        {"timestamp": call.timestamp, **call.model_dump()}
    )

    stated = f"${call.cost_usd:.6f}" if call.cost_usd is not None else "not stated"
    failure = "" if call.error is None else f" (error: {call.error})"
    logger.info(
        f"LLM call: {call.gateway} {call.model} {call.prompt_name} - "
        f"in {call.input_tokens}, out {call.output_tokens}, cost {stated}{failure}"
    )


def sum_cost(calls: list[dict]) -> Decimal:
    """What these calls cost, as their providers stated it.

    A call whose provider stated no cost — the grounded Gemini ones — contributes nothing: it
    is absent, not zero. Takes rows rather than a run id so the eval reports, which hold their
    own already-read list, sum them the same way the cap does.
    """
    return sum(
        (call['cost_usd'] for call in calls if call['cost_usd'] is not None),
        Decimal('0.0'),
    )


def total_cost(pipeline_run_id: str) -> Decimal:
    """What this run has spent so far.

    Sums the in-memory tracker, never `costs.json`: the per-scrape cap reads this mid-run,
    before that file exists.
    """
    return sum_cost(get_cost_tracker(pipeline_run_id)['llm_costs'])


def log_costs(pipeline_run_id, jurisdiction_ocdid):
    """Write the run's calls out, one row each, and drop the tracker.

    No summary alongside them: the only consumer was the Sheets push, deleted 2026-09-04, and a
    stored total is a second place for the same number to be wrong.
    """
    llm_costs = get_cost_tracker(pipeline_run_id)['llm_costs']

    data_path = data_path_utils.get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    costs_file_path = os.path.join(data_path, "costs.json")

    with open(costs_file_path, mode='w') as file:
        file.write(json.dumps({"llm_costs": llm_costs}, indent=4, default=str))

    _COSTS_BY_RUN.pop(pipeline_run_id, None)


