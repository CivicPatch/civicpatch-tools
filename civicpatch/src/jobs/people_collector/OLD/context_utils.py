import json
import os
import aiofiles
from typing import Optional
from shared.utils import data_path_utils
from jobs.people_collector.schemas import (
    PeopleCollectorContext
)
from pipelines.config_utils import (
    load_config_from_file, 
    merge_config_into_context, 
    save_config_to_file, 
)

def load_context_from_file(jurisdiction_id: str) -> Optional[PeopleCollectorContext]:
    context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)
    
    if not os.path.exists(context_file_path):
        return None
    
    try:
        with open(context_file_path, "r") as f:
            context_data = json.load(f)
            return PeopleCollectorContext.model_validate(context_data)
    except Exception as e:
        print(f"Warning: Could not load context: {e}")
        return None

async def save_context_to_file(context: PeopleCollectorContext) -> None:
    jurisdiction_id = context.jurisdiction_id
    context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)
    
    try:
        async with aiofiles.open(context_file_path, "w") as f:
            serialized_context = context.model_dump_json(indent=4, ensure_ascii=False)
            if serialized_context:
                await f.write(serialized_context)
    except Exception as e:
        print(f"Exception in save_context: {e}")

def _apply_config_priority(context: PeopleCollectorContext, jurisdiction_id: str, pipeline_request: PipelineRequest) -> PeopleCollectorContext:
    """Apply config priority: file config first, then request config (higher priority)"""
    # Start with file config (lower priority)
    config_data = load_config_from_file(jurisdiction_id)
    
    # Merge request config if present (higher priority)
    if pipeline_request.config:
        save_config_to_file(jurisdiction_id, pipeline_request.config)
        # Convert PipelineConfig to dict before merging - Request config overwrites file config
        request_config_dict = pipeline_request.config.model_dump(exclude_none=True)
        config_data.update(request_config_dict)
    
    # Single merge operation
    return merge_config_into_context(context, config_data)

def create_pipeline_context(request_id: str, pipeline_request: PipelineRequest) -> PeopleCollectorContext:
    jurisdiction_id = pipeline_request.jurisdiction_id
    
    # Create base context
    context = PeopleCollectorContext(
        request_id=request_id,
        jurisdiction_id=jurisdiction_id,
        state=pipeline_request.state,
        config=pipeline_request.config,
        identities=pipeline_request.config.identities or {}
    )
    
    return _apply_config_priority(context, jurisdiction_id, pipeline_request)

def load_or_create_context(request_id: str, pipeline_request: PipelineRequest) -> PeopleCollectorContext:
    jurisdiction_id = pipeline_request.jurisdiction_id
    
    # Ensure directory exists
    context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)
    os.makedirs(os.path.dirname(context_file_path), exist_ok=True)
    
    # Load existing context if not INIT
    if pipeline_request.state != PipelineStatus.INIT:
        existing_context = load_context_from_file(jurisdiction_id)
        if existing_context:
            existing_context.request_id = request_id
            existing_context.state = pipeline_request.state
            return _apply_config_priority(existing_context, jurisdiction_id, pipeline_request)
    
    # Create new context
    return create_pipeline_context(request_id, pipeline_request)