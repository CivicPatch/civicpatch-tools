from schemas import PipelineRequest, PipelineStatus
import asyncio
from pipelines.pipeline_manager import PipelineManager

pipeline_manager = PipelineManager()


async def test_pipeline_step():
    # jurisdiction_id = "ocd_jurisdiction/country:us/state:nc/place:greensboro/government"
    # jurisdiction_id = "ocd_jurisdiction/country:us/state:wa/place:seattle/government"
    jurisdiction_id = "ocd_jurisdiction/country:us/state:il/place:chicago/government"
    # Note: need to generate a unique request id
    # if you are testing PR creation
    pipeline_manager.create_pipeline(
        PipelineRequest(
            jurisdiction_id=jurisdiction_id,
            name="Chicago city",
            url="https://chicago.gov",
            state=PipelineStatus.CLEANUP,
        )
    )
    pipeline_manager.start_pipeline(jurisdiction_id)


if __name__ == "__main__":
    asyncio.run(test_pipeline_step())
