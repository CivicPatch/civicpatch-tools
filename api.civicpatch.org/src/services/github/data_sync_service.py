import asyncio
import json
import os
from datetime import timezone
from pathlib import Path
from typing import List

import dateutil.parser
import yaml

import database.database as database
import services.github.github_api_service as github_service
import shared
import shared.utils.config_utils as config_utils
import shared.utils.id_utils
from schemas.requests import OdSyncRequestSchema
import logging

logger = logging.getLogger(__name__)

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
    metadata_by_id = jurisdictions_metadata.get("jurisdictions_by_id", {})
    result = {}

    for entry in jurisdiction_entries.get("jurisdictions", []):
        ocdid = entry.get("id")
        if not ocdid:
            continue
        jurisdiction_metadata = metadata_by_id.get(ocdid, {})
        jurisdiction_metadata["jurisdiction"] = entry
        result[ocdid] = jurisdiction_metadata

    logger.debug(f"Returning metadata for state {state}: {list(result.keys())}")
    return result


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
    inactive_ocdids: List[str] = []
    logger.debug(f"Syncing jurisdictions with metadata for OCDIDs: {jurisdiction_ocdids}")
    for jurisdiction_ocdid in jurisdiction_ocdids:
        jurisdiction_data = jurisdiction_metadata.get(jurisdiction_ocdid)
        logger.debug(f"Jurisdiction data for {jurisdiction_ocdid}: {jurisdiction_data}")
        parsed_ocdid = shared.utils.id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
        state = parsed_ocdid.state
        updated_at = jurisdiction_data.get("updated_at") if jurisdiction_data else None
        nested_jurisdiction_data = jurisdiction_data.get("jurisdiction") if jurisdiction_data else None
        if not nested_jurisdiction_data:
            logger.warning(f"No jurisdiction entry found for {jurisdiction_ocdid}, marking as inactive")
            inactive_ocdids.append(jurisdiction_ocdid)
            continue
        serialized_data = json.dumps(nested_jurisdiction_data)
        jurisdictions.append((jurisdiction_ocdid, state, "can-delete", serialized_data, updated_at, "can-delete"))

    logger.debug(f"Prepared {len(jurisdictions)} jurisdictions for bulk update.")
    if inactive_ocdids:
        await database.mark_jurisdictions_inactive(inactive_ocdids)
    await database.bulk_update_jurisdictions(jurisdictions)


async def sync_people_by_ocdids(jurisdiction_ocdids):
    logger.info(f"Syncing people data for OCDIDs: {jurisdiction_ocdids}")
    semaphore = asyncio.Semaphore(10)

    async def _fetch(jurisdiction_ocdid):
        folder_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
        people_file_path = os.path.join("data", f"{folder_path}.yml")
        async with semaphore:
            remote_data = await github_service.get_github_file_contents(people_file_path)
        remote_data_list = yaml.safe_load(remote_data) if remote_data else None
        if not remote_data_list:
            return []
        return [
            (person.get("id"), jurisdiction_ocdid, people_file_path, json.dumps(person), person.get("updated_at"), "dummy_git_commit_hash")
            for person in remote_data_list
        ]

    results = await asyncio.gather(*[_fetch(ocdid) for ocdid in jurisdiction_ocdids])
    people_list = [row for rows in results for row in rows]
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
        has_no_people = not local_jurisdiction_data or local_jurisdiction_data.get("people_count", 0) == 0
        if has_no_people or is_newer(remote_updated_at, local_jurisdiction_data.get("updated_at") if local_jurisdiction_data else None):
            jurisdictions_to_update_data.append(jurisdiction_ocdid)
        await asyncio.sleep(0)

    remote_ocdids = set(all_jurisdiction_metadata.keys())
    local_ocdids = set(local_jurisdictions.keys())

    ocdids_to_delete = local_ocdids - remote_ocdids
    if ocdids_to_delete:
        logger.info(f"Deleting jurisdictions with OCDIDs: {ocdids_to_delete}")
        await database.deactivate_jurisdictions_by_ocdids(list(ocdids_to_delete))

    logger.info(f"Updating metadata for jurisdictions with OCDIDs: {len(jurisdictions_to_update_metadata)}")
    logger.debug(f"OCDIDs to update metadata: {jurisdictions_to_update_metadata}")
    await sync_jurisdictions_by_ocdids_with_metadata(all_jurisdiction_metadata, jurisdictions_to_update_metadata)

    logger.info(f"Updating people data for jurisdictions with OCDIDs: {jurisdictions_to_update_data}")
    await sync_people_by_ocdids(jurisdictions_to_update_data)


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
