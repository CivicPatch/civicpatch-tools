from typing import List
from pipeline import Pipeline, PipelineStatus
from schemas import PipelineRequest
from fastapi import BackgroundTasks
from utils import id_utils

class PipelineManager:
    def __init__(self):
        self._pipelines: dict[str, Pipeline] = {}

    def add_pipeline(self, pipeline_request: PipelineRequest):
        pipeline = Pipeline(
            request_id=id_utils.make_request_id(),
            pipeline_request=pipeline_request,
            remove_callback=self.remove_pipeline  # Pass the callback
        )
        self._pipelines[pipeline_request.jurisdiction_id] = pipeline

    def get_pipeline(self, jurisdiction_id: str) -> Pipeline | None:
        return self._pipelines.get(jurisdiction_id)

    def remove_pipeline(self, jurisdiction_id: str):
        if jurisdiction_id in self._pipelines:
            del self._pipelines[jurisdiction_id]

    def pause_pipeline(self, jurisdiction_id: str):
        pipeline = self.get_pipeline(jurisdiction_id)
        if pipeline:
            pipeline.pause_requested = True
            print(f"Pipeline for jurisdiction {jurisdiction_id} paused.")
        else:
            print(f"No pipeline found for jurisdiction {jurisdiction_id}.")

    def create_pipeline(self, pipeline_request: PipelineRequest):
        """Create a new pipeline without starting it."""
        request_id = id_utils.make_request_id()
        jurisdiction_id = pipeline_request.jurisdiction_id
        warnings: List[str] = []
        errors: List[str] = []

        # Validate the request
        jurisdiction_id_obj = id_utils.parse_jurisdiction_id(jurisdiction_id)
        if not jurisdiction_id_obj:
            errors.append(f"Invalid jurisdiction_id format: {jurisdiction_id}.")
        if not pipeline_request.name:
            warnings.append("Missing 'name' field. Substituting with place name jurisdiction_id.")
        if not pipeline_request.url:
            errors.append("Missing 'url' field.")

        if len(errors) > 0:
            return request_id, warnings, errors

        self.add_pipeline(pipeline_request)

        print(f"New pipeline for jurisdiction {jurisdiction_id} created.")

        return request_id, warnings, errors

    def start_pipeline(self, jurisdiction_id: str, background_tasks: BackgroundTasks):
        """Start an existing pipeline."""
        pipeline = self.get_pipeline(jurisdiction_id)
        if not pipeline:
            raise ValueError(f"No pipeline found for jurisdiction {jurisdiction_id}.")

        # pipeline.pause_requested = False  # Reset pause flag 

        #if pipeline.context.state in [PipelineStatus.PAUSE, # Pipeline was paused, now we want to restart it
        #                              PipelineStatus.DONE, # Pipeline has finished
        #                              PipelineStatus.INIT # We have never started this pipeline before
        #                              ]:  # We paused it now we want to restart it
        #    # Run the existing pipeline in the background
        background_tasks.add_task(pipeline.run)
        return {"status": "started", "jurisdiction_id": jurisdiction_id}
    
    def stop_pipeline(self, jurisdiction_id: str):
        pipeline = self.get_pipeline(jurisdiction_id)
        if not pipeline:
            raise ValueError(f"No pipeline found for jurisdiction {jurisdiction_id}.")
        
        pipeline.stop_requested = True  # Set stop flag
        self.remove_pipeline(jurisdiction_id)
        return {"status": "stopping", "jurisdiction_id": jurisdiction_id}