import argparse
import asyncio
import json
import sys
from interfaces.schemas import (
    PeopleCollectorJobRequest,
    validate_people_request
)
from runners.people_collector.schemas import PipelineRunConfig
from runners.engine import PipelineRunError
from runners.people_collector.main import start as start_people_collector
from shared.utils import id_utils
from pipelines_environment import get_env_vars
from services.civicpatch_api import get_jurisdiction_info


async def run_pipeline_cli(request_id: str, request: PeopleCollectorJobRequest):
    warnings, errors = validate_people_request(request)
    if errors:
        print("Errors:", errors)
        sys.exit(1)
    if warnings:
        for warning in warnings:
            print(f"Warning: {warning}")

    try:
        await start_people_collector(
            request_id=request_id,
            jurisdiction_ocdid=request.jurisdiction_ocdid,
            config=request.config,
        )
    except PipelineRunError:
        sys.exit(1)  # Already logged in people_collector.main
    except Exception:
        sys.exit(1)  # Already logged in people_collector.main

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
        "--jurisdiction-ocdid", required=True, help="Jurisdiction ID"
    )
    run_pipeline_parser.add_argument(
        "--name", required=False, default=None, help="Name of the municipality"
    )
    run_pipeline_parser.add_argument(
        "--url", required=False, default=None, help="URL of the city council page"
    )
    run_pipeline_parser.add_argument(
        "--request-id", required=False, help="Optional request ID"
    )
    run_pipeline_parser.add_argument(
        "--source-urls", required=False, help="JSON array of specific URLs to scrape"
    )

    args = parser.parse_args()

    if args.command == "run_pipeline":
        request_id = args.request_id or id_utils.make_request_id()

        source_urls = json.loads(args.source_urls) if args.source_urls else None
        name = args.name
        url = args.url
        if not name or not url:
            info = asyncio.run(get_jurisdiction_info(args.jurisdiction_ocdid))
            name = name or info.get("name")
            url = url or info.get("url")
        request = PeopleCollectorJobRequest(
            jurisdiction_ocdid=args.jurisdiction_ocdid,
            config=PipelineRunConfig(
                name=name,
                url=url or "",
                source_urls=source_urls,
            ),
        )
        asyncio.run(run_pipeline_cli(request_id, request))
    else:
        print(f"cli command not available: {args.command}")


if __name__ == "__main__":
    main()
