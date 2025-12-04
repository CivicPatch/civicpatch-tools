import os
import yaml
from datetime import datetime, timezone
from typing import Dict, Any
from schemas import PipelineConfig, PipelineContext
from shared.utils import data_path_utils

def load_config_from_file(jurisdiction_id: str) -> Dict[str, Any]:
    config_file_path = data_path_utils.get_config_file_path(jurisdiction_id)
    
    if not os.path.exists(config_file_path):
        return {}
    
    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return {}

def save_config_to_file(jurisdiction_id: str, config_updates: PipelineConfig) -> None:
    config_file_path = data_path_utils.get_config_file_path(jurisdiction_id)
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)
    
    existing_config = load_config_from_file(jurisdiction_id)
    
    # Convert PipelineConfig to dict before merging
    config_updates_dict = config_updates.model_dump(exclude_none=True) if config_updates else {}
    
    # Merge updates with existing
    updated_config = {**existing_config, **config_updates_dict}
    updated_config["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    with open(config_file_path, "w", encoding="utf-8") as f:
        yaml.dump(updated_config, f, allow_unicode=True, sort_keys=False, indent=4)

def merge_config_into_context(context: PipelineContext, config: Dict[str, Any]) -> PipelineContext:
    context_dict = context.model_dump()
    
    # Only merge config fields that exist in the PipelineContext model
    valid_fields = set(PipelineContext.model_fields.keys())
    filtered_config = {k: v for k, v in config.items() if k in valid_fields}
    
    context_dict.update(filtered_config)
    
    return PipelineContext.model_validate(context_dict)