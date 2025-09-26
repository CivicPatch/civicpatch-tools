from schemas import PipelineContext, PipelineRequest, PipelineStatus
from pipeline import Pipeline
from utils.data_path_utils import get_pipeline_context_file_path
import os
import json
import asyncio

async def test_pipeline_step():
    jurisdiction_id = "ocd_jurisdiction/country:us/state:nc/place:greensboro"
    pipeline_status = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
    # Note: need to generate a unique request id
    # if you are testing PR creation
    request_id = "bbbbbbbbbbbbbb"

    pipeline = Pipeline()
    pipeline.set_state(pipeline_status)

    # Update pipeline_context_path with request_id
    pipeline_context_path = get_pipeline_context_file_path(jurisdiction_id)

    with open(pipeline_context_path, "r") as f:
        context = json.load(f)
        context["request_id"] = request_id
    with open(pipeline_context_path, "w") as f:
        json.dump(context, f, indent=2)

    pipeline_request = PipelineRequest(
        jurisdiction_id=jurisdiction_id, 
        name="Test", 
        url="http://example.com"
    )
    await pipeline.run_async(request_id, pipeline_request)

if __name__ == "__main__":
    asyncio.run(test_pipeline_step())