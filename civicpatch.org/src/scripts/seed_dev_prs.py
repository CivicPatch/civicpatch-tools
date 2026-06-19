"""
Seed the dev database with open pull requests from GitHub.

For each PR, this script:
  - Seeds jurisdiction data from the open-data repo
  - Creates requests / pipeline_runs / pull_requests rows
  - Backfills data_json from the PR branch

Merging a seeded PR from the dev review UI merges the real GitHub PR.
Production will pick up the merge via webhook and sync people as normal.
The dev server skips people sync (env label mismatch).

Usage:
    uv run python src/scripts/seed_dev_prs.py [--limit N]
"""

import argparse
import asyncio
import logging

import psycopg.errors
import shared.utils.id_utils as id_utils
import lib.github.api as github_service
from services.open_data_sync import sync_jurisdictions_by_ocdids
from services.pull_request_sync import maybe_backfill_job_result
from database.requests import register_foreign_request

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10


def _jurisdiction_ocdid_from_branch(branch: str) -> str | None:
    try:
        parts = id_utils.git_branch_to_parts(branch)
    except ValueError:
        return None

    if "jurisdiction_ocdid" in parts:
        return parts["jurisdiction_ocdid"]

    # New branch format: "job/{folder}/{request_id}" — reconstruct ocdid from folder
    if branch.startswith("job/"):
        segments = branch.split("/")
        folder = "/".join(segments[1:-1])
        try:
            return id_utils.folder_to_jurisdiction_ocdid(folder)
        except ValueError:
            return None

    return None


async def seed_dev_prs(limit: int = DEFAULT_LIMIT):
    logger.info("Fetching open PRs from GitHub...")
    all_prs = await github_service.get_all_open_prs_raw()
    logger.info("Found %d open PR(s), seeding up to %d", len(all_prs), limit)

    seeded = 0
    skipped = 0

    for pr in all_prs:
        if seeded >= limit:
            break

        branch = pr.get("head", {}).get("ref", "")
        pr_url = pr.get("html_url")

        try:
            parts = id_utils.git_branch_to_parts(branch)
        except ValueError:
            logger.debug("Skipping branch (unrecognised format): %s", branch)
            continue

        request_id = parts.get("request_id")
        jurisdiction_ocdid = _jurisdiction_ocdid_from_branch(branch)

        if not request_id or not jurisdiction_ocdid:
            logger.debug("Skipping PR — could not derive request_id or jurisdiction_ocdid from %s", branch)
            continue

        logger.info("[%d/%d] Seeding %s (%s)", seeded + 1, limit, jurisdiction_ocdid, request_id)

        await sync_jurisdictions_by_ocdids([jurisdiction_ocdid])
        try:
            await register_foreign_request(request_id, jurisdiction_ocdid, pr_url, "github")
        except psycopg.errors.UniqueViolation:
            logger.info("Already in DB, refreshing data for %s", request_id)
            skipped += 1

        await maybe_backfill_job_result(request_id)

        seeded += 1

    logger.info("Done — seeded %d PR(s), skipped %d already present", seeded, skipped)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed dev database with open PRs from GitHub")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of PRs to seed (default: {DEFAULT_LIMIT})",
    )
    args = parser.parse_args()
    asyncio.run(seed_dev_prs(limit=args.limit))
