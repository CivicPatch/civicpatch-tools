import os
import csv
from utils import data_path_utils
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timezone

llm_model_prices = {
    'openai': {
        'openai/gpt-4.1-mini': {
            'input_cost_per_1m': Decimal('0.40'),
            'output_cost_per_1m': Decimal('1.60')
        }
    },
    'gemini': {
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

@dataclass
class LLMCost:
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

@dataclass
class SearchEngineCost:
    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec='seconds')
    jurisdiction_id: str
    search_engine_name: str

    @property
    def total_cost(self) -> Decimal:
        cost_per_thousand = search_engine_prices.get(self.search_engine_name, Decimal('0.0'))
        return (cost_per_thousand / Decimal(1000))


# For images/zip files
@dataclass
class StorageCost:
    @property
    def timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec='seconds')

    jurisdiction_id: str

    storage_gb: Decimal
    image_size_bytes: int

    @property
    def storage_cost(self) -> Decimal:
        return self.storage_gb * storage_prices['by_monthly_gb']

def log_llm_cost(
        jurisdiction_id: str, 
        llm_name: str, 
        model: str, 

        input_tokens: int, 
        output_tokens: int, 
        with_search=False
):
    result = LLMCost(
        timestamp=data_path_utils.get_current_timestamp(),
        jurisdiction_id=jurisdiction_id,
        llm_name=llm_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        with_search=with_search
    )

    log_path = data_path_utils.get_data_source_municipality_path(jurisdiction_id)
    is_new_file = not os.path.exists(log_path)

    with open(log_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if is_new_file:
            writer.writerow([
                "timestamp", 
                "jurisdiction_id", 
                "llm_name", 
                "model", 
                "model_input_price_per_1m",
                "model_output_price_per_1m",
                "input_tokens", 
                "output_tokens", 
                "with_search",
                "input_cost", 
                "output_cost", 
                "total_cost"
            ])
        model_input_cost = llm_model_prices.get(llm_name, {}).get(model, {}).get('input_cost_per_1m', Decimal('0.0'))
        model_output_cost = llm_model_prices.get(llm_name, {}).get(model, {}).get('output_cost_per_1m', Decimal('0.0'))

        writer.writerow([
            result.timestamp,
            result.jurisdiction_id,
            result.llm_name,
            result.model,
            f"{model_input_cost:.6f}",
            f"{model_output_cost:.6f}",
            result.input_tokens,
            result.output_tokens,
            result.with_search,
            f"{result.input_cost:.6f}",
            f"{result.output_cost:.6f}",
            f"{result.total_cost:.6f}"
        ])

def log_search_engine_cost(
        jurisdiction_id: str, 
        search_engine_name: str, 
        num_requests: int = 1
):
    result = SearchEngineCost(
        timestamp=data_path_utils.get_current_timestamp(),
        jurisdiction_id=jurisdiction_id,
        search_engine_name=search_engine_name,
        num_requests=num_requests
    )

    log_path = data_path_utils.get_costs_log_path(jurisdiction_id)
    is_new_file = not os.path.exists(log_path)

    with open(log_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if is_new_file:
            writer.writerow([
                "timestamp", 
                "jurisdiction_id", 
                "search_engine_name", 
                "per_1000_requests_price",
                "total_cost"
            ])
        cost_per_1000_requests = search_engine_prices.get(search_engine_name, Decimal('0.0'))

        writer.writerow([
            result.timestamp,
            result.jurisdiction_id,
            result.search_engine_name,
            f"{cost_per_1000_requests:.6f}",
            f"{result.total_cost:.6f}"
        ])

def log_storage_cost(
        jurisdiction_id: str, 
        storage_gb: Decimal, 
        image_size_bytes: int
):
    result = StorageCost(
        timestamp=data_path_utils.get_current_timestamp(),
        jurisdiction_id=jurisdiction_id,
        storage_gb=storage_gb,
        image_size_bytes=image_size_bytes
    )

    log_path = data_path_utils.get_costs_log_path(jurisdiction_id)
    is_new_file = not os.path.exists(log_path)

    with open(log_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if is_new_file:
            writer.writerow([
                "timestamp", 
                "jurisdiction_id", 
                "monthly_storage_gb_price"
                "storage_gb", 
                "image_size_bytes",
                "storage_cost"
            ])
        writer.writerow([
            result.timestamp,
            result.jurisdiction_id,
            f"{storage_prices['by_monthly_gb']:.6f}",
            f"{result.storage_gb:.6f}",
            result.image_size_bytes,
            f"{result.storage_cost:.6f}"
        ])