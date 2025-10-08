import os
import json
from utils import data_path_utils
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timezone
from pydantic import BaseModel

_COSTS_BY_JURISDICTION = {}

llm_model_prices = {
    'openai': {
        'openai/gpt-4.1-mini': {
            'input_cost_per_1m': Decimal('0.40'),
            'output_cost_per_1m': Decimal('1.60')
        }
    },
    'google_gemini': {
        'gemini-2.5-flash': {
            'input_cost_per_1m': Decimal('0.30'),
            'output_cost_per_1m': Decimal('2.50'),
            # Do we need to calculate this? 1500 requests free
            # So 500 municipalities free before it starts costing anything
            # 'with_search': 
        },
        'gemini-2.5-flash-preview-09-2025': {
            'input_cost_per_1m': Decimal('0.30'),
            'output_cost_per_1m': Decimal('2.50')
        },
        'gemini-2.5-flash-lite': {
            'input_cost_per_1m': Decimal('0.10'),
            'output_cost_per_1m': Decimal('0.40')
        }
    },
    'together_ai': {
        'mistralai/Mixtral-8x7B-Instruct-v0.1': {
            'input_cost_per_1m': Decimal('0.60'),
            'output_cost_per_1m': Decimal('0.60')
        }
    }
}

# https://developers.cloudflare.com/r2/pricing/
storage_prices = {
    'by_monthly_gb': Decimal('0.015'),  # $0.015 per GB per month
    'by_traffic_requests_per_million': Decimal('0.36')  # $0.36 per million requests
}

# https://developers.google.com/custom-search/v1/overview
# Limit 10k queries/day
search_engine_prices = {
    'google': Decimal('5.00')  # $5.00 per 1000 requests
}

class LLMCost(BaseModel):
    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    jurisdiction_id: str
    llm_name: str
    model: str
    
    input_tokens: int
    output_tokens: int
    with_search: bool = False # Sometimes not available

    @property
    def input_cost_per_1m(self) -> Decimal:
        llm_prices = llm_model_prices.get(self.llm_name, {})
        model_prices = llm_prices.get(self.model, {})
        return model_prices.get('input_cost_per_1m', Decimal('0.0'))    
    
    @property
    def output_cost_per_1m(self) -> Decimal:
        llm_prices = llm_model_prices.get(self.llm_name, {})
        model_prices = llm_prices.get(self.model, {})
        return model_prices.get('output_cost_per_1m', Decimal('0.0'))

    @property
    def input_cost(self) -> Decimal:
        llm_prices = llm_model_prices.get(self.llm_name, {})
        model_prices = llm_prices.get(self.model, {})
        cost_per_1m = model_prices.get('input_cost_per_1m', Decimal('0.0'))
        return (Decimal(self.input_tokens) / Decimal(1_000_000)) * cost_per_1m

    @property
    def output_cost(self) -> Decimal:
        llm_prices = llm_model_prices.get(self.llm_name, {})
        model_prices = llm_prices.get(self.model, {})
        cost_per_1m = model_prices.get('output_cost_per_1m', Decimal('0.0'))
        return (Decimal(self.output_tokens) / Decimal(1_000_000)) * cost_per_1m

    @property
    def total_cost(self) -> Decimal:
        return self.input_cost + self.output_cost

class SearchEngineCost(BaseModel):
    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    @property
    def cost_per_1000_requests(self) -> Decimal:
        return search_engine_prices.get(self.search_engine_name, Decimal('0.0'))

    jurisdiction_id: str
    search_engine_name: str

    @property
    def total_cost(self) -> Decimal:
        cost_per_thousand = search_engine_prices.get(self.search_engine_name, Decimal('0.0'))
        return (cost_per_thousand / Decimal(1000))


# For images/zip files
class StorageCost(BaseModel):
    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec='seconds')
    
    @property
    def price_per_gb(self) -> Decimal:
        return storage_prices['by_monthly_gb']

    jurisdiction_id: str

    file_size_bytes: int

    @property
    def total_cost(self) -> Decimal:
        size_in_gb = bytes_to_gb(self.file_size_bytes)
        return size_in_gb * storage_prices['by_monthly_gb']

def get_cost_tracker(jurisdiction_id: str):
    if jurisdiction_id not in _COSTS_BY_JURISDICTION:
        _COSTS_BY_JURISDICTION[jurisdiction_id] = {
            'llm_costs': [],
            'search_engine_costs': [],
            'storage_costs': []
        }
    return _COSTS_BY_JURISDICTION[jurisdiction_id]

def add_llm_cost(
        jurisdiction_id: str, 
        llm_name: str, 
        model: str, 

        input_tokens: int, 
        output_tokens: int, 
        with_search=False
):
    result = LLMCost(
        jurisdiction_id=jurisdiction_id,
        llm_name=llm_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        with_search=with_search
    )

    # HEADERS = [
    #     "timestamp", 
    #     "jurisdiction_id", 
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
    cost_tracker = get_cost_tracker(jurisdiction_id)
    cost_tracker['llm_costs'].append({
        "timestamp": result.timestamp,
        "jurisdiction_id": result.jurisdiction_id,
        "llm_name": result.llm_name,
        "model": result.model,
        "model_input_price_per_1m": llm_model_prices.get(result.llm_name, {}).get(result.model, {}).get('input_cost_per_1m', Decimal('0.0')),
        "model_output_price_per_1m": llm_model_prices.get(result.llm_name, {}).get(result.model, {}).get('output_cost_per_1m', Decimal('0.0')),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "with_search": result.with_search,
        "input_cost": result.input_cost,
        "output_cost": result.output_cost,
        "total_cost": result.total_cost
    })

def add_search_engine_cost(
        jurisdiction_id: str, 
        search_engine_name: str, 
):
    # HEADERS = [
    #     "timestamp", 
    #     "jurisdiction_id", 
    #     "search_engine_name", 
    #     "per_1000_requests_price",
    #     "total_cost"
    # ]
    result = SearchEngineCost(
        jurisdiction_id=jurisdiction_id,
        search_engine_name=search_engine_name,
    )

    cost_per_1000_requests = search_engine_prices.get(search_engine_name, Decimal('0.0'))
    cost_tracker = get_cost_tracker(jurisdiction_id)
    cost_tracker['search_engine_costs'].append({
        "timestamp": result.timestamp,
        "jurisdiction_id": result.jurisdiction_id,
        "search_engine_name": result.search_engine_name,
        "per_1000_requests_price": cost_per_1000_requests,
        "total_cost": result.total_cost
    })

def bytes_to_gb(size_bytes: int) -> Decimal:
    return Decimal(size_bytes) / Decimal(1024 ** 3)

def add_storage_cost(
        jurisdiction_id: str, 
        file_size_bytes: int
):
    
    # HEADERS = [
    #     "timestamp", 
    #     "jurisdiction_id", 
    #     "monthly_storage_gb_price"
    #     "storage_gb", 
    #     "image_size_bytes",
    #     "storage_cost"
    # ]
    result = StorageCost(
        jurisdiction_id=jurisdiction_id,
        file_size_bytes=file_size_bytes
    )

    cost_tracker = get_cost_tracker(jurisdiction_id)
    cost_tracker['storage_costs'].append({
        "timestamp": result.timestamp,
        "jurisdiction_id": result.jurisdiction_id,
        "monthly_storage_gb_price": storage_prices['by_monthly_gb'],
        "file_size_bytes": result.file_size_bytes,
        "total_cost": result.total_cost,
    })

def log_costs(jurisdiction_id):
    cost_tracker = get_cost_tracker(jurisdiction_id)
    llm_costs = cost_tracker['llm_costs']
    search_engine_costs = cost_tracker['search_engine_costs']
    storage_costs = cost_tracker['storage_costs']

    data_path = data_path_utils.get_data_source_municipality_path(jurisdiction_id)
    costs_file_path = os.path.join(data_path, "costs.json")

    with open(costs_file_path, mode='w', newline='') as file:
        json_object = json.dumps({
            "llm_costs": llm_costs,
            "search_engine_costs": search_engine_costs,
            "storage_costs": storage_costs,
            "total_cost": sum(
                [item['total_cost'] for item in llm_costs]
                + [item['total_cost'] for item in search_engine_costs]
                # TBD search engine 
            )

        }, indent=4, default=str)
        file.write(json_object)
    
    _COSTS_BY_JURISDICTION.pop(jurisdiction_id, None)

    
        