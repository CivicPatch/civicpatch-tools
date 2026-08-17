"""Keeping a jurisdiction's URL current when a scrape finds it has moved.

A scrape resolves the URL it was given, following redirects, and the resolved value is what it
actually read. When that differs from the registry, the registry is stale — a council site
moved and nothing told us. Recording it is how `data_source/<state>/local/jurisdictions.yml`
stops rotting.

This used to live in open-data, as a step of `data_intake.yml` (update_jurisdiction_url.py)
run against the unpacked artifact. It moves here because that workflow is going away with the
scrape pull requests, and losing it would mean scrapes silently stop correcting stale URLs.

Written as a direct commit rather than a pull request: a redirect the scraper followed is an
observation, not a proposal, and there is no human decision for a PR to carry.
"""

import logging

import core.jurisdiction_patch as jurisdiction_patch
import lib.github.api as github_service
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.yaml_utils import yaml_dump, yaml_load

logger = logging.getLogger(__name__)


def jurisdictions_file_path(jurisdiction_ocdid: str) -> str:
    parsed = parse_jurisdiction_ocdid(jurisdiction_ocdid)
    return f"data_source/{parsed.state}/{parsed.level}/jurisdictions.yml"


def resolved_url(workflow_context: dict) -> str | None:
    """The URL the scrape actually read, after redirects. None when the run recorded no config,
    which is the shape of a run that failed before it got that far."""
    config = (workflow_context or {}).get("data", {}).get("config") or {}
    return config.get("url")


async def record_resolved_url(jurisdiction_ocdid: str, url: str) -> bool:
    """Point the registry at where the scrape actually found the jurisdiction.

    Returns True when a commit was made. A URL that already matches is not an error and not a
    commit — the file is only written when it would change, so the history stays a record of
    real moves rather than a heartbeat.
    """
    file_path = jurisdictions_file_path(jurisdiction_ocdid)
    raw = await github_service.get_github_file_contents(file_path)
    if not raw:
        logger.warning(f"Could not read {file_path}; leaving the URL alone")
        return False

    # Round-tripped through ruamel, so quotes, comments and layout survive: this touches one
    # value in a file listing every jurisdiction in the state.
    doc = yaml_load(raw)
    entry = jurisdiction_patch.find_jurisdiction(doc, jurisdiction_ocdid)
    if entry is None:
        logger.warning(f"{jurisdiction_ocdid} is not listed in {file_path}")
        return False

    patch = jurisdiction_patch.build_patch({"url": url})
    if not patch or jurisdiction_patch.current_values(entry, patch) == patch:
        return False

    was = entry.get("url")
    committed = await github_service.upsert_github_file(
        branch_name=github_service.DEFAULT_BRANCH,
        file_path=file_path,
        content_str=yaml_dump(
            jurisdiction_patch.apply_patch(doc, jurisdiction_ocdid, patch)
        ),
        commit_message=f"Update url for {jurisdiction_ocdid}: {was} -> {url}",
    )
    if not committed:
        logger.error(f"Failed to write the resolved URL for {jurisdiction_ocdid}")
        return False

    logger.info(f"{jurisdiction_ocdid} url: {was} -> {url}")
    return True
