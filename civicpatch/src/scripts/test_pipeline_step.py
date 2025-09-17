from schemas import PipelineContext, PipelineStatus
from pipeline import Pipeline
from utils.data_path_utils import get_pipeline_context_file_path
import os
import json

def test_pipeline_step():
    state = "wa"
    geoid = "5363000"  # Seattle
    pipeline_status = PipelineStatus.MAYBE_SEND_TO_GITHUB
    # Note: need to generate a unique request id
    # if you are testing PR creation
    request_id = "c3bcb6d3-a391-49b2-9f60-b51d5df69bea"

    pipeline = Pipeline()
    pipeline.set_state(pipeline_status)

    # Update pipeline_context_path with request_id
    pipeline_context_path = get_pipeline_context_file_path(state, geoid)

    with open(pipeline_context_path, "r") as f:
        context = json.load(f)
        context["request_id"] = request_id
    with open(pipeline_context_path, "w") as f:
        json.dump(context, f, indent=2)

    pipeline.run(request_id, state, geoid) 

if __name__ == "__main__":
    test_pipeline_step()