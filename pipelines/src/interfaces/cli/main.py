import argparse
import asyncio
import json
from decimal import Decimal
import sys

import httpx

from interfaces.schemas import (
    PeopleCollectorRequest,
    validate_people_request
)
from runners.people_collector.schemas import PipelineRunConfig
from runners.engine import PipelineRunError
from runners.people_collector.main import start as start_people_collector
from shared.utils import id_utils
from pipelines_environment import get_env_vars
from services.civicpatch_api import get_jurisdiction_info, register_pipeline_run


async def run_pipeline_cli(pipeline_run_id: str, request: PeopleCollectorRequest):
    warnings, errors = validate_people_request(request)
    if errors:
        print("Errors:", errors)
        sys.exit(1)
    if warnings:
        for warning in warnings:
            print(f"Warning: {warning}")

    try:
        await start_people_collector(
            pipeline_run_id=pipeline_run_id,
            jurisdiction_ocdid=request.jurisdiction_ocdid,
            config=request.config,
        )
    except PipelineRunError:
        sys.exit(1)  # Already logged in people_collector.main
    except Exception:
        sys.exit(1)  # Already logged in people_collector.main

async def _run_pipeline_async(args):
    pipeline_run_id = args.pipeline_run_id or id_utils.make_id()
    source_urls = json.loads(args.source_urls) if args.source_urls else None
    name = args.name
    url = args.url

    env = get_env_vars()
    async with httpx.AsyncClient(headers={"Authorization": env["SERVICE_API_KEY"]}, timeout=30.0) as client:
        if not name or not url:
            info = await get_jurisdiction_info(client, args.jurisdiction_ocdid)
            name = name or info.get("name")
            url = url or info.get("url")
        await register_pipeline_run(client, pipeline_run_id, args.jurisdiction_ocdid, name, url)

    request = PeopleCollectorRequest(
        jurisdiction_ocdid=args.jurisdiction_ocdid,
        config=PipelineRunConfig(
            name=name,
            url=url or "",
            source_urls=source_urls,
            # Blank, not just absent: the workflow always passes the flag and sends an empty
            # string when no state set a cap, so `or None` is what keeps that meaning inherit.
            pipeline_run_cap_usd=Decimal(args.pipeline_run_cap_usd) if args.pipeline_run_cap_usd else None,
        ),
    )
    await run_pipeline_cli(pipeline_run_id, request)


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
        # data_scrape.yml in CivicPatch/server invokes this flag by name.
        "--pipeline-run-id", required=False, help="Optional pipeline run ID"
    )
    run_pipeline_parser.add_argument(
        "--source-urls", required=False, help="JSON array of specific URLs to scrape"
    )
    run_pipeline_parser.add_argument(
        "--pipeline-run-cap-usd",
        required=False,
        help="Ceiling for this run, in USD. Omitted or blank inherits pipeline.yml's default.",
    )

    args = parser.parse_args()

    if args.command == "run_pipeline":
        asyncio.run(_run_pipeline_async(args))
    else:
        print(f"cli command not available: {args.command}")


if __name__ == "__main__":
    main()
