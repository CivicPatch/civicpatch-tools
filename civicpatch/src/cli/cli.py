import argparse
import asyncio
import os
from typing import List

from pipelines.main import get_pipeline_manager
from pipelines.pipeline import Pipeline
from schemas import PipelineRequest
from utils import id_utils

pipeline_manager = get_pipeline_manager()

CRUDDER_URL = os.getenv("CRUDDER_URL")
CRUDDER_SHARED_TOKEN = os.getenv("CRUDDER_SHARED_TOKEN")


async def run_pipeline_cli(request: PipelineRequest):
    request_id = id_utils.make_request_id()
    jurisdiction_id = id_utils.parse_jurisdiction_id(request.jurisdiction_id)
    warnings: List[str] = []
    errors: List[str] = []

    if not jurisdiction_id:
        errors.append(f"Invalid jurisdiction_id format: {request.jurisdiction_id}")
    if not request.name:
        warnings.append(
            "Missing 'name' field: A name and legal status (e.g., 'Seattle city') is preferred for search purposes. Substituting with place name jurisdiction_id."
        )
    if not request.url:
        errors.append("Missing 'url' field")

    for warning in warnings:
        print(f"Warning: {warning}")

    if errors:
        print("Errors:", errors)
    else:
        print(f"Request ID: {request_id}")
        pipeline = Pipeline(
            request_id,
            request,
            remove_callback=None,
        )
        await pipeline.run_async()


def main():
    parser = argparse.ArgumentParser(
        description="CLI for managing pipelines and jurisdictions"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: get_juds
    get_juds_parser = subparsers.add_parser(
        "get_juds", help="Get available jurisdictions by population and state"
    )
    get_juds_parser.add_argument(
        "--num-jurisdictions",
        required=True,
        help="Number of jurisdictions to fetch",
    )
    get_juds_parser.add_argument(
        "--state",
        required=True,
        help="State to filter jurisdictions by",
    )

    # Subcommand: run_pipeline
    run_pipeline_parser = subparsers.add_parser(
        "run_pipeline", help="Run a pipeline for a municipality"
    )
    run_pipeline_parser.add_argument(
        "--jurisdiction-id", required=True, help="Jurisdiction ID"
    )
    run_pipeline_parser.add_argument(
        "--name", required=True, help="Name of the municipality"
    )
    run_pipeline_parser.add_argument(
        "--url", required=True, help="URL of the city council page"
    )

    args = parser.parse_args()

    if args.command == "run_pipeline":
        request = PipelineRequest(
            jurisdiction_id=args.jurisdiction_id, name=args.name, url=args.url
        )
        asyncio.run(run_pipeline_cli(request))
    else:
        print(f"cli command not available: {args.command}")


if __name__ == "__main__":
    main()
