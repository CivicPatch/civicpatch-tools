from schemas import PipelineContext, PipelineStatus
from pipeline import Pipeline

def test_pipeline_step():
    pipeline = Pipeline()
    pipeline.set_state(PipelineStatus.CLEANUP)
    pipeline.run("test_request_id", "wa", "5363000") 

if __name__ == "__main__":
    test_pipeline_step()