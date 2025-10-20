from schemas import PipelineRequest, PipelineStatus
from pipeline import Pipeline
from utils.data_path_utils import get_pipeline_context_file_path
import json
import asyncio
import uuid
from pipeline_manager import PipelineManager

pipeline_manager = PipelineManager()

async def test_pipeline_step():
    #jurisdiction_id = "ocd_jurisdiction/country:us/state:nc/place:greensboro/government"
    jurisdiction_id = "ocd_jurisdiction/country:us/state:wa/place:seattle/government"
    # Note: need to generate a unique request id
    # if you are testing PR creation
    pipeline_manager.create_pipeline(
        PipelineRequest(
            jurisdiction_id=jurisdiction_id,
            name="Seattle city",
            url="https://seattle.gov/council",
            state=PipelineStatus.MAYBE_SEND_TO_GITHUB
        ))
    pipeline_manager.start_pipeline(jurisdiction_id)

if __name__ == "__main__":
    asyncio.run(test_pipeline_step())