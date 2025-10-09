from schemas import PipelineRequest, PipelineStatus
from pipeline import Pipeline
from utils.data_path_utils import get_pipeline_context_file_path
import json
import asyncio
import uuid

async def test_pipeline_step():
    jurisdiction_id = "ocd_jurisdiction/country:us/state:nc/place:greensboro/council"
    pipeline_status = PipelineStatus.MAYBE_SEND_TO_GITHUB
    # Note: need to generate a unique request id
    # if you are testing PR creation
    request_id = f"test_pipeline_{str(uuid.uuid4())}"

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
    await pipeline.run_async(request_id, pipeline_request, with_debug=True)

if __name__ == "__main__":
    asyncio.run(test_pipeline_step())