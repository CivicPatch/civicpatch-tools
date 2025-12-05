from typing import List
from pipelines.pipeline import Pipeline
from schemas import PipelineRequest
from fastapi import BackgroundTasks
from shared.utils import id_utils

from urllib.parse import urlparse
import asyncio


class PipelineManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._pipelines: dict[str, Pipeline] = {}
            self._initialized = True

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
        if not pipeline_request.config.name:
            warnings.append(
                "Missing 'name' field. Substituting with place name jurisdiction_id."
            )
        if not pipeline_request.config.url:
            errors.append("Missing 'url' field.")

        # Check all webpage_urls, if present, are valid URLs
        if pipeline_request.config.source_urls:
            for url in pipeline_request.config.source_urls:
                parse_url = urlparse(url)
                is_valid_url = all([parse_url.scheme, parse_url.netloc])
                if not is_valid_url:
                    errors.append(f"Invalid URL in source_urls: {url}") 

        if len(errors) > 0:
            return request_id, warnings, errors

        self.add_pipeline(request_id, pipeline_request)

        print(f"New pipeline for jurisdiction {jurisdiction_id} created.")

        return request_id, warnings, errors

    async def start_pipeline(
        self,
        request_id: str,
        pipeline_request: PipelineRequest,
        background_tasks: BackgroundTasks,
    ):
        errors = []
        warnings = []
        pipeline = self.get_pipeline(pipeline_request.jurisdiction_id)
        if not pipeline:
            errors.append(f"No pipeline found for jurisdiction {pipeline_request.jurisdiction_id}.")
            return request_id, warnings, errors

        pipeline.stop_requested = False  # Reset stop flag

        if background_tasks:
            background_tasks.add_task(pipeline.run)
        else:
            await pipeline.run_async()

        return request_id, warnings, errors

    async def create_start_pipeline(
        self,
        pipeline_request: PipelineRequest,
        background_tasks: BackgroundTasks | None = None,
    ):
        """Create and start a new pipeline."""
        errors = []
        request_id, warnings, errors = self.create_pipeline(pipeline_request)
        if len(errors) > 0:
            return request_id, warnings, errors

        request_id, warnings, errors = await self.start_pipeline(
            request_id, pipeline_request, background_tasks
        )
        
        return request_id, warnings, errors

    def stop_pipeline(self, jurisdiction_id: str):
        pipeline = self.get_pipeline(jurisdiction_id)
        if not pipeline:
            raise ValueError(f"No pipeline found for jurisdiction {jurisdiction_id}.")

        pipeline.stop_requested = True  # Set stop flag
        return {"status": "stopping", "jurisdiction_id": jurisdiction_id}
