import os
import json
from shared.schemas import LLMCall
from shared.utils import data_path_utils
from utils import log_utils
from decimal import Decimal

# One run's calls, in the order they were made. Typed all the way through: the model was
# previously dumped to a dict the moment it arrived, which cost every reader its types for
# nothing — `costs.json` is the only thing that needs plain data, and only at the very end.
_CALLS_BY_RUN: dict[str, list[LLMCall]] = {}


def reset_cost_tracker(pipeline_run_id: str) -> None:
    """Drop a run's accumulated costs.

    Only needed by callers that reuse one id across measurements — the evals do. A real
    scrape gets a fresh run id, so its tally starts empty without anyone remembering to ask.
    """
    _CALLS_BY_RUN.pop(pipeline_run_id, None)


def get_cost_tracker(pipeline_run_id: str) -> list[LLMCall]:
    """Keyed on the run, not the jurisdiction.

    Keyed on the jurisdiction, two runs for the same place in one process shared a tally and
    the second inherited the first's — the eval provider comparison read input tokens as
    exactly double for byte-identical work. A run id makes that impossible rather than
    leaving a `reset_cost_tracker` call to remember.
    """
    return _CALLS_BY_RUN.setdefault(pipeline_run_id, [])


def record_call(
    logger: log_utils.PipelineRunLogger, pipeline_run_id: str, call: LLMCall
) -> None:
    """Add one call to this run's tally. The model crosses the boundary, not fifteen arguments."""
    get_cost_tracker(pipeline_run_id).append(call)

    stated = f"${call.cost_usd:.6f}" if call.cost_usd is not None else "not stated"
    failure = "" if call.error is None else f" (error: {call.error})"
    logger.info(
        f"LLM call: {call.gateway} {call.model} {call.prompt_name} - "
        f"in {call.input_tokens}, out {call.output_tokens}, cost {stated}{failure}"
    )


def sum_cost(calls: list[LLMCall]) -> Decimal:
    """What these calls cost, as their providers stated it.

    A call whose provider stated no cost — the grounded Gemini ones — contributes nothing: it
    is absent, not zero. Takes the calls rather than a run id so the eval reports, which hold
    their own list, sum them the same way the cap does.
    """
    return sum(
        (call.cost_usd for call in calls if call.cost_usd is not None),
        Decimal('0.0'),
    )


def total_cost(pipeline_run_id: str) -> Decimal:
    """What this run has spent so far.

    Sums the in-memory tracker, never `costs.json`: the per-scrape cap reads this mid-run,
    before that file exists.
    """
    return sum_cost(get_cost_tracker(pipeline_run_id))


def log_costs(pipeline_run_id, jurisdiction_ocdid):
    """Write the run's calls out, one row each, and drop the tracker.

    The single point where the models become plain data — `civicpatch.org` reads this file back
    into `llm_calls` using the very same model's field list.

    No summary alongside them: the only consumer was the Sheets push, deleted 2026-09-04, and a
    stored total is a second place for the same number to be wrong.
    """
    calls = get_cost_tracker(pipeline_run_id)

    data_path = data_path_utils.get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    costs_file_path = os.path.join(data_path, "costs.json")

    with open(costs_file_path, mode='w') as file:
        file.write(
            json.dumps(
                {"llm_costs": [call.model_dump() for call in calls]}, indent=4, default=str
            )
        )

    _CALLS_BY_RUN.pop(pipeline_run_id, None)
