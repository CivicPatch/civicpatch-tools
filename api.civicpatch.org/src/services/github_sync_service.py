#!/usr/bin/env python3
"""
Daily sync script to update PostgreSQL database with changed files from Git repo
Compatible with existing psycopg_pool AsyncConnectionPool setup
"""

import asyncio
import json
import os
from pathlib import Path
from typing import List

import dateutil.parser
import httpx
import yaml

import database.database as database
import services.cache_service as cache_service
import services.github_service as github_service
import shared
import shared.utils.config_utils as config_utils
import shared.utils.id_utils
from datetime import timezone
from schemas.requests import OdSyncRequestSchema
import logging
logger = logging.getLogger(__name__)

import environment

# Configuration
REPO_URL = "https://github.com/CivicPatch/open-data.git"
REPO_PATH = Path("/app/git_data")
DATA_FILES_PATTERNS = [
    "data/*/local/*.yml",
    "data/*/counties/*.yml",
]
JURISDICTION_FILES_PATTERN = "data_source/**/jurisdictions_metadata.yml"
MAP_FILES_PATTERN = "data/**/.maps/*.geojson"

async def get_jurisdiction_metadata(state: str):
    jurisdictions_file_path = os.path.join("data_source", state, "jurisdictions.yml")
    jurisdictions_metadata_file_path = os.path.join("data_source", state, "jurisdictions_metadata.yml")
    logger.debug(f"Fetching jurisdictions_metadata from: {jurisdictions_metadata_file_path}")
    jurisdictions_metadata_response = await github_service.get_github_file_contents(jurisdictions_metadata_file_path)
    logger.debug(f"Fetching jurisdiction_entries from: {jurisdictions_file_path}")
    jurisdiction_entries_response = await github_service.get_github_file_contents(jurisdictions_file_path)

    if not jurisdictions_metadata_response or not jurisdiction_entries_response:
        logger.warning(f"Missing data for state {state}: "
                       f"metadata_response={bool(jurisdictions_metadata_response)}, "
                       f"entries_response={bool(jurisdiction_entries_response)}")
        return None

    jurisdictions_metadata = yaml.safe_load(jurisdictions_metadata_response)
    jurisdiction_entries = yaml.safe_load(jurisdiction_entries_response)
    logger.debug(f"Loaded jurisdictions_metadata keys: {list(jurisdictions_metadata.keys())}")
    logger.debug(f"Loaded jurisdiction_entries keys: {list(jurisdiction_entries.keys())}")
    metadata = jurisdictions_metadata.get("jurisdictions_by_id", {})

    for jurisdiction_ocdid, jurisdiction_metadata in metadata.items():
        jurisdictions = jurisdiction_entries.get("jurisdictions", [])
        jurisdiction_entry = next((entry for entry in jurisdictions if entry.get("id") == jurisdiction_ocdid), None)
        if jurisdiction_entry:
            jurisdiction_metadata["jurisdiction"] = jurisdiction_entry

    logger.debug(f"Returning metadata for state {state}: {list(metadata.keys())}")
    return metadata

async def get_jurisdiction_metadata_for_ocdids(jurisdiction_ocdids: List[str]) -> dict:
    jurisdiction_metadata_by_state = {}
    logger.debug(f"Getting jurisdiction metadata for OCDIDs: {jurisdiction_ocdids}")
    for jurisdiction_ocdid in jurisdiction_ocdids:
        parsed_ocdid = shared.utils.id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
        state = parsed_ocdid.state
        if state not in jurisdiction_metadata_by_state:
            jurisdiction_metadata_by_state[state] = await get_jurisdiction_metadata(state)
    logger.debug(f"jurisdiction_metadata_by_state keys: {list(jurisdiction_metadata_by_state.keys())}")
    return jurisdiction_metadata_by_state

async def sync_jurisdictions_by_ocdids(jurisdiction_ocdids: List[str]):
    logger.info(f"Syncing jurisdictions by OCDIDs: {jurisdiction_ocdids}")
    jurisdiction_metadata_by_state = await get_jurisdiction_metadata_for_ocdids(jurisdiction_ocdids)
    await sync_jurisdictions_by_ocdids_with_metadata(jurisdiction_metadata_by_state, jurisdiction_ocdids)

async def sync_jurisdictions_by_ocdids_with_metadata(jurisdiction_metadata, jurisdiction_ocdids: List[str]):
    jurisdictions: List[tuple] = []
    logger.debug(f"Syncing jurisdictions with metadata for OCDIDs: {jurisdiction_ocdids}")
    for jurisdiction_ocdid in jurisdiction_ocdids:
        jurisdiction_data = jurisdiction_metadata.get(jurisdiction_ocdid)
        logger.debug(f"Jurisdiction data for {jurisdiction_ocdid}: {jurisdiction_data}")
        parsed_ocdid = shared.utils.id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
        state = parsed_ocdid.state
        updated_at = jurisdiction_data.get("updated_at") if jurisdiction_data else None
        nested_jurisdiction_data = jurisdiction_data.get("jurisdiction") if jurisdiction_data else None
        serialized_data = json.dumps(nested_jurisdiction_data) if nested_jurisdiction_data else None
        jurisdictions.append((jurisdiction_ocdid, state, "can-delete", serialized_data, updated_at, "can-delete"))

    logger.debug(f"Prepared {len(jurisdictions)} jurisdictions for bulk update.")
    await database.bulk_update_jurisdictions(jurisdictions)

async def sync_people_by_ocdids(jurisdiction_ocdids):
    logger.info(f"Syncing people data for OCDIDs: {jurisdiction_ocdids}")
    people_list: List[tuple] = []
    for jurisdiction_ocdid in jurisdiction_ocdids:
        folder_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
        people_file_path = os.path.join("data", f"{folder_path}.yml")
        logger.debug(f"Fetching people file: {people_file_path}")
        remote_data = await github_service.get_github_file_contents(people_file_path)
        remote_data_list = yaml.safe_load(remote_data) if remote_data else None

        if remote_data_list:
            logger.debug(f"Loaded {len(remote_data_list)} people for {jurisdiction_ocdid}")
            for person in remote_data_list:
                person_id = person.get("id")
                updated_at = person.get("updated_at")
                serialized_data = json.dumps(person)
                people_list.append((person_id, jurisdiction_ocdid, people_file_path, serialized_data, updated_at, "dummy_git_commit_hash"))
        else:
            logger.debug(f"No people data found for {jurisdiction_ocdid}")

    logger.debug(f"Prepared {len(people_list)} people for bulk update.")
    await database.bulk_update_people(people_list)

async def bulk_sync():
    logger.info("Starting bulk sync")
    states_config = config_utils.get_states()
    states = [state["code"] for state in states_config]
    all_jurisdiction_metadata = {}

    for state in states:
        logger.debug(f"Fetching remote metadata for state: {state}")
        remote_metadata_file = await get_jurisdiction_metadata(state)
        logger.debug(f"Remote metadata keys for {state}: {list(remote_metadata_file.keys()) if remote_metadata_file else 'None'}")
        all_jurisdiction_metadata = {**all_jurisdiction_metadata, **remote_metadata_file}
        await asyncio.sleep(0)

    local_jurisdictions = await database.get_jurisdiction_updates()
    logger.debug(f"Local jurisdictions keys: {list(local_jurisdictions.keys())}")

    jurisdictions_to_update_metadata = []
    jurisdictions_to_update_data = []

    for jurisdiction_ocdid in all_jurisdiction_metadata:
        remote_updated_at = all_jurisdiction_metadata[jurisdiction_ocdid].get("updated_at")
        jurisdictions_to_update_metadata.append(jurisdiction_ocdid)
        local_jurisdiction_data = local_jurisdictions.get(jurisdiction_ocdid)
        if is_newer(remote_updated_at, local_jurisdiction_data.get("updated_at") if local_jurisdiction_data else None):
            jurisdictions_to_update_data.append(jurisdiction_ocdid)
        await asyncio.sleep(0)

    remote_ocdids = set(all_jurisdiction_metadata.keys())
    local_ocdids = set(local_jurisdictions.keys())

    ocdids_to_delete = local_ocdids - remote_ocdids
    if ocdids_to_delete:
        logger.info(f"Deleting jurisdictions with OCDIDs: {ocdids_to_delete}")
        await database.delete_jurisdictions_by_ocdids(list(ocdids_to_delete))

    logger.info(f"Updating metadata for jurisdictions with OCDIDs: {len(jurisdictions_to_update_metadata)}")
    logger.debug(f"OCDIDs to update metadata: {jurisdictions_to_update_metadata}")
    await sync_jurisdictions_by_ocdids_with_metadata(all_jurisdiction_metadata, jurisdictions_to_update_metadata)

    logger.info(f"Updating people data for jurisdictions with OCDIDs: {jurisdictions_to_update_data}")
    await sync_people_by_ocdids(jurisdictions_to_update_data)

async def backfill_job_result(request_id: str, jurisdiction_ocdid: str):
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    data = await github_service.get_pull_request_file_yaml(
        request_id, jurisdiction_ocdid, f"data/{folder}.yml"
    )
    if data is None:
        logger.warning("backfill_job_result: no file found for %s", request_id)
        return
    await database.update_job_result(request_id, data)
    logger.info("backfill_job_result: result_json set for %s", request_id)


async def sync_open_pr_state():
    logger.info("sync_open_pr_state: starting")
    _, _, _, open_data_repo_url = github_service._get_github_config()
    github_request_ids: set[str] = set()
    page = 1
    per_page = 100

    # request_id -> {url, jurisdiction_ocdid}
    github_prs: dict[str, dict] = {}

    while True:
        url = f"{open_data_repo_url}/pulls?state=open&per_page={per_page}&page={page}"
        headers = await github_service.get_default_headers()
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            logger.error(f"sync_open_pr_state: GitHub API error on page {page}: {response.status_code}")
            break

        prs = response.json()
        for pr in prs:
            branch_name = pr.get("head", {}).get("ref", "")
            try:
                parts = shared.utils.id_utils.git_branch_to_parts(branch_name)
                github_prs[parts["request_id"]] = {
                    "url": pr.get("html_url"),
                    "jurisdiction_ocdid": parts["jurisdiction_ocdid"],
                }
            except (ValueError, KeyError):
                pass

        if len(prs) < per_page:
            break
        page += 1
        await asyncio.sleep(0)

    github_request_ids = set(github_prs.keys())
    logger.info(f"sync_open_pr_state: found {len(github_request_ids)} open PRs on GitHub")

    for request_id, pr_info in github_prs.items():
        updated = await database.update_job_pull_request_status(
            request_id, "open", None, pull_request_url=pr_info["url"]
        )
        if not updated:
            logger.info(f"sync_open_pr_state: no job found for {request_id}, creating")
            await database.register_job(
                requested_by_provider="github_sync",
                requested_by_provider_user_id="github_sync",
                request_id=request_id,
                job_type="people",
                arguments_json={"jurisdiction_ocdid": pr_info["jurisdiction_ocdid"]},
                jurisdiction_ocdid=pr_info["jurisdiction_ocdid"],
                status="completed",
                progress=100,
            )
            await database.update_job_pull_request_status(
                request_id, "open", None, pull_request_url=pr_info["url"]
            )
            await backfill_job_result(request_id, pr_info["jurisdiction_ocdid"])

    db_open_ids = await database.get_open_pr_request_ids()
    stale_ids = [rid for rid in db_open_ids if rid not in github_request_ids]
    if stale_ids:
        logger.info(f"sync_open_pr_state: closing {len(stale_ids)} stale PR(s)")
        await database.bulk_close_stale_prs(stale_ids)

    logger.info("sync_open_pr_state: done")


async def sync(request: OdSyncRequestSchema):
    jurisdiction_ocdids = request.jurisdiction_ocdids
    logger.info(f"Sync request for OCDIDs: {jurisdiction_ocdids}")
    if jurisdiction_ocdids:
        await sync_jurisdictions_by_ocdids(jurisdiction_ocdids)
        await sync_people_by_ocdids(jurisdiction_ocdids)
    else:
        await bulk_sync()

def is_newer(date1, date2):
    if not date1:
        return False
    if not date2:
        return True
    dt1 = dateutil.parser.parse(date1)
    dt2 = dateutil.parser.parse(date2)
    if dt1.tzinfo is None:
        dt1 = dt1.replace(tzinfo=timezone.utc)
    if dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    return dt1 > dt2
