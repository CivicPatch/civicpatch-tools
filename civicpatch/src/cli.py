import argparse
import asyncio
from typing import List
from utils import id_utils
from schemas import PipelineRequest, PipelineStatus
from pipeline import Pipeline

async def run_pipeline_cli(request: PipelineRequest):
    request_id = id_utils.make_request_id()
    jurisdiction_id = id_utils.parse_jurisdiction_id(request.jurisdiction_id)
    warnings: List[str] = []
    errors: List[str] = []

    if not jurisdiction_id:
        errors.append(f"Invalid jurisdiction_id format: {request.jurisdiction_id}")
    if not request.name:
        warnings.append("Missing 'name' field: A name and legal status (e.g., 'Seattle city') is preferred for search purposess. Substituting with place name jurisdiction_id.")
    if not request.url:
        errors.append("Missing 'url' field")

    for warning in warnings:
        print(f"Warning: {warning}")

    if errors:
        print("Errors:", errors)
    else:
        print(f"Request ID: {request_id}")
        pipeline = Pipeline(pipeline_state=PipelineStatus.INIT)
        await pipeline.run_async(request_id, request)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run pipeline for a municipality")
    parser.add_argument("--jurisdiction-id", required=True, help="Jurisdiction ID")
    parser.add_argument("--name", required=True, help="Name of the municipality")
    parser.add_argument("--url", required=True, help="URL of the city council page")
    args = parser.parse_args()

    request = PipelineRequest(
        jurisdiction_id=args.jurisdiction_id,
        name=args.name,
        url=args.url
    )
    asyncio.run(run_pipeline_cli(request))