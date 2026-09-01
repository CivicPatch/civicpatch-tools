import os
import json
from shared.utils import data_path_utils
from utils import log_utils
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel

_COSTS_BY_JURISDICTION = {}

llm_model_prices = {
    'google_gemini': {
        'gemini-2.5-flash': {
            'input_cost_per_1m': Decimal('0.30'),
            'output_cost_per_1m': Decimal('2.50'),
            # Do we need to calculate this? 1500 requests free
            # So 500 municipalities free before it starts costing anything
            # 'with_search': 
        },
        'gemini-3.1-flash-lite-preview': {
            'input_cost_per_1m': Decimal('0.25'),
            'output_cost_per_1m': Decimal('1.50')
        }
    },
    # open_router prices are per (model, provider)
    # Key is the model alias sent in the request (not the versioned slug OpenRouter returns)
    #
    # An unlisted (model, provider) pair costs Decimal('0.0') — see _model_prices below.
    # That is silent, so a model bump without a matching entry here reports zero spend
    # rather than failing. Requests pin allow_fallbacks=False and name their providers, so
    # the routed provider is always one of the ones listed here — but only while this list
    # and llm.py's `order` agree.
    'open_router': {
        # v4-flash prices from OpenRouter's endpoint catalogue, read 2026-08-14.
        # These are the providers in llm.py's order — all support structured_outputs,
        # which strict json_schema requires. SiliconFlow is deliberately absent: it is
        # cheaper ($0.13/$0.28) but only does response_format, so it 404s.
        'deepseek/deepseek-v4-flash': {
            'DigitalOcean':{'input_cost_per_1m': Decimal('0.07'),  'output_cost_per_1m': Decimal('0.17')},
            'DeepInfra':   {'input_cost_per_1m': Decimal('0.09'),  'output_cost_per_1m': Decimal('0.18')},
            'AtlasCloud':  {'input_cost_per_1m': Decimal('0.14'),  'output_cost_per_1m': Decimal('0.28')},
        },
    }
}


def get_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')

class LLMCost(BaseModel):
    @property
    def timestamp(self) -> str:
        return get_timestamp()

    jurisdiction_ocdid: str
    llm_name: str
    model: str
    routed_model: str = ""
    provider: str = ""

    input_tokens: int
    output_tokens: int
    with_search: bool = False

    def _model_prices(self) -> dict:
        llm_prices = llm_model_prices.get(self.llm_name, {})
        model_entry = llm_prices.get(self.model, {})
        # open_router prices are keyed by provider
        if self.llm_name == 'open_router' and self.provider:
            return model_entry.get(self.provider, {})
        return model_entry

    @property
    def input_cost_per_1m(self) -> Decimal:
        return self._model_prices().get('input_cost_per_1m', Decimal('0.0'))

    @property
    def output_cost_per_1m(self) -> Decimal:
        return self._model_prices().get('output_cost_per_1m', Decimal('0.0'))

    @property
    def input_cost(self) -> Decimal:
        return (Decimal(self.input_tokens) / Decimal(1_000_000)) * self.input_cost_per_1m

    @property
    def output_cost(self) -> Decimal:
        return (Decimal(self.output_tokens) / Decimal(1_000_000)) * self.output_cost_per_1m

    @property
    def total_cost(self) -> Decimal:
        return self.input_cost + self.output_cost


def reset_cost_tracker(jurisdiction_ocdid: str):
    """Drop a jurisdiction's accumulated costs.

    `log_costs` already does this at the end of a pipeline run, but anything that measures
    several runs in one process has to do it itself. The provider comparison did not, and
    since every provider uses the same eval ocdid, each report inherited the tally of every
    provider before it — the second provider's input tokens read as exactly double the
    first's for byte-identical work.
    """
    _COSTS_BY_JURISDICTION.pop(jurisdiction_ocdid, None)


def get_cost_tracker(jurisdiction_ocdid: str):
    if jurisdiction_ocdid not in _COSTS_BY_JURISDICTION:
        _COSTS_BY_JURISDICTION[jurisdiction_ocdid] = {
            'llm_costs': [],
        }
    return _COSTS_BY_JURISDICTION[jurisdiction_ocdid]

def add_llm_cost(
        logger: log_utils.PipelineRunLogger,
        changeset_id: str,
        jurisdiction_ocdid: str,
        llm_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        with_search=False,
        provider: str = "",
        routed_model: str = "",
):
    result = LLMCost(
        jurisdiction_ocdid=jurisdiction_ocdid,
        llm_name=llm_name,
        model=model,
        routed_model=routed_model or model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        with_search=with_search,
    )

    # HEADERS = [
    #     "timestamp", 
    #     "jurisdiction_ocdid", 
    #     "llm_name", 
    #     "model", 
    #     "model_input_price_per_1m",
    #     "model_output_price_per_1m",
    #     "input_tokens", 
    #     "output_tokens", 
    #     "with_search",
    #     "input_cost", 
    #     "output_cost", 
    #     "total_cost"
    # ]
    cost_tracker = get_cost_tracker(jurisdiction_ocdid)
    cost_tracker['llm_costs'].append({
        "timestamp": result.timestamp,
        "changeset_id": changeset_id,
        "jurisdiction_ocdid": result.jurisdiction_ocdid,
        "llm_name": result.llm_name,
        "model": result.model,
        "routed_model": result.routed_model,
        "provider": result.provider,
        "model_input_price_per_1m": result.input_cost_per_1m,
        "model_output_price_per_1m": result.output_cost_per_1m,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "with_search": result.with_search,
        "input_cost": result.input_cost,
        "output_cost": result.output_cost,
        "total_cost": result.total_cost
    })
    logger.info(f"LLM Cost added: {result.llm_name} model {result.model} - Input tokens: {input_tokens}, Output tokens: {output_tokens}, Total cost: ${result.total_cost:.6f}")


def total_cost_by_request(changeset_id, jurisdiction_ocdid: str) -> dict[str, Decimal]:
    cost_tracker = get_cost_tracker(jurisdiction_ocdid)
    llm_costs = cost_tracker['llm_costs']
    total_costs_llm = sum([item['total_cost'] for item in llm_costs])

    # Group LLM costs by llm_name only
    grouped_llm_costs = {}
    for item in llm_costs:
        key = item['llm_name']
        if key not in grouped_llm_costs:
            grouped_llm_costs[key] = {
                "timestamp": item['timestamp'],
                "changeset_id": item['changeset_id'],
                "jurisdiction_ocdid": item['jurisdiction_ocdid'],
                "llm_name": item['llm_name'],
                "input_tokens": 0,
                "output_tokens": 0,
                "input_cost": Decimal('0.0'),
                "output_cost": Decimal('0.0'),
                "total_cost": Decimal('0.0')
            }
        grouped_llm_costs[key]['input_tokens'] += item['input_tokens']
        grouped_llm_costs[key]['output_tokens'] += item['output_tokens']
        grouped_llm_costs[key]['input_cost'] += item['input_cost']
        grouped_llm_costs[key]['output_cost'] += item['output_cost']
        grouped_llm_costs[key]['total_cost'] += item['total_cost']

    # Build the total_cost_by_request_id array with dynamic LLM columns
    total_cost_row = {
        "timestamp": get_timestamp(),
        "changeset_id": changeset_id,
        "jurisdiction_ocdid" : jurisdiction_ocdid,
        "total_costs_llm": total_costs_llm,
    }

    # Emit all known LLM columns in a fixed order so the sheet layout is stable
    # regardless of which LLMs were used in a given run
    for llm_name in sorted(llm_model_prices.keys()):
        cost_data = grouped_llm_costs.get(llm_name)
        total_cost_row[f"llm_{llm_name}_cost"] = cost_data['total_cost'] if cost_data else Decimal('0.0')

    total_cost_row["total_cost"] = total_costs_llm
    return total_cost_row

def log_costs(changeset_id, jurisdiction_ocdid):
    cost_tracker = get_cost_tracker(jurisdiction_ocdid)
    llm_costs = cost_tracker['llm_costs']

    data_path = data_path_utils.get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    costs_file_path = os.path.join(data_path, "costs.json")

    total_cost_row = total_cost_by_request(changeset_id, jurisdiction_ocdid)

    with open(costs_file_path, mode='w') as file:
        json_object = json.dumps({
            "llm_costs": llm_costs,
            "total_cost_by_request": total_cost_row
        }, indent=4, default=str)
        file.write(json_object)
    
    _COSTS_BY_JURISDICTION.pop(jurisdiction_ocdid, None)


