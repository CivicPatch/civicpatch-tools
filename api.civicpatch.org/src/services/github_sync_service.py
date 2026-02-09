#!/usr/bin/env python3
"""
Daily sync script to update PostgreSQL database with changed files from Git repo
Compatible with existing psycopg_pool AsyncConnectionPool setup
"""

import asyncio
import json
import os
from pathlib import Path
import services.github_service as github_service

import yaml
import yaml
import database
from typing import List
import shared
import dateutil.parser
from datetime import timezone
import logging
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    "REPO_URL": "https://github.com/CivicPatch/open-data.git",
    "REPO_PATH": Path("/app/git_data"),
    "DATA_FILES_PATTERNS": [
        "data/*/local/*.yml",
        "data/*/counties/*.yml",
    ],
    "JURISDICTION_FILES_PATTERN": "data_source/**/jurisdictions_metadata.yml",
    "MAP_FILES_PATTERN": "data/**/.maps/*.geojson",
    "CRUDDER_DB_URL": os.getenv("CRUDDER_DB_URL"),
}

# Use config values throughout the file
REPO_URL = CONFIG["REPO_URL"]
REPO_PATH = CONFIG["REPO_PATH"]
DATA_FILES_PATTERNS = CONFIG["DATA_FILES_PATTERNS"]
JURISDICTION_FILES_PATTERN = CONFIG["JURISDICTION_FILES_PATTERN"]
MAP_FILES_PATTERN = CONFIG["MAP_FILES_PATTERN"]
CRUDDER_DB_URL = CONFIG["CRUDDER_DB_URL"]

# Check for required environment variable before attempting to create pool
if not CRUDDER_DB_URL:
    raise ValueError("CRUDDER_DB_URL environment variable is not set.")

async def get_jurisdiction_metadata(state: str):
    file_path = os.path.join("data_source", state, "jurisdictions_metadata.yml")
    jurisdictions_metadata_file = await github_service.get_github_file_contents(file_path)
    if not jurisdictions_metadata_file:
        return None
    data = yaml.safe_load(jurisdictions_metadata_file)
    jurisdictions_metadata = data.get("jurisdictions_by_id", {})

    return jurisdictions_metadata

async def get_jurisdiction_metadata_for_ocdids(jurisdiction_ocdids: List[str]) -> dict:
    jurisdiction_metadata_by_state = {}
    for jurisdiction_ocdid in jurisdiction_ocdids:
        parsed_ocdid = shared.utils.id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
        state = parsed_ocdid.state
        if state not in jurisdiction_metadata_by_state:
            jurisdiction_metadata_by_state[state] = await get_jurisdiction_metadata(state)
    return jurisdiction_metadata_by_state


async def sync_jurisdictions_by_ocdids(jurisdiction_ocdids: List[str]):
    jurisdiction_metadata_by_state = await get_jurisdiction_metadata_for_ocdids(jurisdiction_ocdids)
    sync_jurisdictions_by_ocdids_with_metadata(jurisdiction_metadata_by_state, jurisdiction_ocdids)

async def sync_jurisdictions_by_ocdids_with_metadata(jurisdiction_metadata, jurisdiction_ocdids: List[str]):
    jurisdictions: List[tuple] = []
    for jurisdiction_ocdid in jurisdiction_ocdids:
        jurisdiction_data = jurisdiction_metadata.get(jurisdiction_ocdid)

        parsed_ocdid = shared.utils.id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
        state = parsed_ocdid.state
        updated_at = jurisdiction_data.get("updated_at") if jurisdiction_data else None
        nested_jurisdiction_data = jurisdiction_data.get("jurisdiction") if jurisdiction_data else None
        serialized_data = json.dumps(nested_jurisdiction_data) if nested_jurisdiction_data else None
        jurisdictions.append((jurisdiction_ocdid, state, "can-delete", serialized_data, updated_at, "can-delete"))

    await database.bulk_update_jurisdictions(jurisdictions)

async def sync_people_by_ocdids(jurisdiction_ocdids):
    logging.info(f"Syncing people data for OCDIDs: {jurisdiction_ocdids}")
    people_list: List[tuple] = []
    for jurisdiction_ocdid in jurisdiction_ocdids:
        folder_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
        people_file_path = os.path.join("data", f"{folder_path}.yml")
        remote_data = await github_service.get_github_file_contents(people_file_path)
        remote_data_list = yaml.safe_load(remote_data) if remote_data else None

        first_updated_at = remote_data_list[0].get("updated_at") if remote_data_list and len(remote_data_list) > 0 else None
        serialized_data = json.dumps(remote_data_list) if remote_data_list else None
        people_list.append((jurisdiction_ocdid, "can-delete", serialized_data, first_updated_at, "can-delete"))

    await database.bulk_update_people(people_list)

async def bulk_sync():
    states = await database.get_states()
    all_jurisdiction_metadata = {}

    for state in states:
        remote_metadata_file = await get_jurisdiction_metadata(state)

        all_jurisdiction_metadata = {**all_jurisdiction_metadata, **remote_metadata_file}

    local_jurisdictions = await database.get_jurisdiction_updates()
    local_people = await database.get_people_updates()

    jurisdictions_to_update_metadata = []
    jurisdictions_to_update_data = []

    for jurisdiction_ocdid in all_jurisdiction_metadata:
        remote_updated_at = all_jurisdiction_metadata[jurisdiction_ocdid].get("updated_at")

        local_jurisdiction = local_jurisdictions.get(jurisdiction_ocdid)
        local_people_data = local_people.get(jurisdiction_ocdid)

        if is_newer(remote_updated_at, local_jurisdiction.get("updated_at") if local_jurisdiction else None):
            jurisdictions_to_update_metadata.append(jurisdiction_ocdid)

        if is_newer(remote_updated_at, local_people_data.get("updated_at") if local_people_data else None):
            jurisdictions_to_update_data.append(jurisdiction_ocdid)

    remote_ocdids = set(all_jurisdiction_metadata.keys())
    local_ocdids = set(local_jurisdictions.keys())

    # Jurisdictions to delete
    ocdids_to_delete = local_ocdids - remote_ocdids
    if ocdids_to_delete:
        logger.info(f"Deleting jurisdictions with OCDIDs: {ocdids_to_delete}")
        await database.delete_jurisdictions_by_ocdids(list(ocdids_to_delete))

    logger.info(f"Updating metadata for jurisdictions with OCDIDs: {jurisdictions_to_update_metadata}")
    await sync_jurisdictions_by_ocdids_with_metadata(all_jurisdiction_metadata, jurisdictions_to_update_metadata)

    logger.info(f"Updating people data for jurisdictions with OCDIDs: {jurisdictions_to_update_data}")
    await sync_people_by_ocdids(jurisdictions_to_update_data)

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

async def main():
    # TBD: implement main sync logic when no jurisdiction_ocdids are provided
    pass

if __name__ == "__main__":
    asyncio.run(main())
