from typing import List
from pipelines.pipeline import Pipeline
from schemas import PipelineRequest
from fastapi import BackgroundTasks
from utils import id_utils
import asyncio


class PipelineManager:
    def __init__(self):
        self._pipelines: dict[str, Pipeline] = {}

    def add_pipeline(self, request_id, pipeline_request: PipelineRequest):
        pipeline = Pipeline(
            request_id=request_id,
            pipeline_request=pipeline_request,
            remove_callback=self.remove_pipeline,  # Pass the callback
        )
        self._pipelines[pipeline_request.jurisdiction_id] = pipeline

    def get_pipeline(self, jurisdiction_id: str) -> Pipeline | None:
        return self._pipelines.get(jurisdiction_id)

    def remove_pipeline(self, jurisdiction_id: str):
        if jurisdiction_id in self._pipelines:
            del self._pipelines[jurisdiction_id]

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
            warnings.append(
                "Missing 'name' field. Substituting with place name jurisdiction_id."
            )
        if not pipeline_request.url:
            errors.append("Missing 'url' field.")

        if len(errors) > 0:
            return request_id, warnings, errors

        self.add_pipeline(request_id, pipeline_request)

        print(f"New pipeline for jurisdiction {jurisdiction_id} created.")

        return request_id, warnings, errors

    def start_pipeline(
        self, jurisdiction_id: str, background_tasks: BackgroundTasks | None = None
    ):
        """Start an existing pipeline."""
        pipeline = self.get_pipeline(jurisdiction_id)
        if not pipeline:
            raise ValueError(f"No pipeline found for jurisdiction {jurisdiction_id}.")

        pipeline.stop_requested = False  # Reset stop flag
        if background_tasks:
            background_tasks.add_task(pipeline.run)
        else:
            asyncio.create_task(pipeline.run_async())
        return {"status": "started", "jurisdiction_id": jurisdiction_id}

    def stop_pipeline(self, jurisdiction_id: str):
        pipeline = self.get_pipeline(jurisdiction_id)
        if not pipeline:
            raise ValueError(f"No pipeline found for jurisdiction {jurisdiction_id}.")

        pipeline.stop_requested = True  # Set stop flag
        return {"status": "stopping", "jurisdiction_id": jurisdiction_id}
