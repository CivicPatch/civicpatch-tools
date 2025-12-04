import argparse
import asyncio
import os
from typing import List

from pipelines.pipeline_manager import PipelineManager
from pipelines.pipeline import Pipeline
from schemas import PipelineRequest

pipeline_manager = PipelineManager()

API_CIVICPATCH_ORG_URL = os.getenv("API_CIVICPATCH_ORG_URL")
API_CIVICPATCH_ORG_TOKEN = os.getenv("API_CIVICPATCH_ORG_TOKEN")


async def run_pipeline_cli(request: PipelineRequest):
    request_id, warnings, errors = await pipeline_manager.create_start_pipeline(request)

    for warning in warnings:
        print(f"Warning: {warning}")

    if errors:
        print("Errors:", errors)
    else:
        print(f"Request ID: {request_id}")

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
            jurisdiction_id=args.jurisdiction_id, 
            config={
                "name": args.name,
                "url": args.url,
            }
        )
        asyncio.run(run_pipeline_cli(request))
    else:
        print(f"cli command not available: {args.command}")


if __name__ == "__main__":
    main()
