#!/usr/bin/env python3
"""
Daily sync script to update PostgreSQL database with changed files from Git repo
Compatible with existing psycopg_pool AsyncConnectionPool setup
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import github_service as github_service

import yaml
import aiofiles
import aiofiles.os
import fnmatch
import aiofiles
import yaml
import database
from typing import List, Optional
import shared
import dateutil.parser
from datetime import timezone

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

async def sync_jurisdiction_definitions(states: List[str]):
    jurisdiction_ocdids_to_update = set()
    for state in states:
        file_path = os.path.join("data_source", state, "jurisdictions_metadata.yml")
        jurisdictions_metadata_file = await github_service.get_github_file_contents(file_path)
        jurisdictions_metadata = yaml.safe_load(jurisdictions_metadata_file)

        for jurisdiction in jurisdictions_metadata.get("jurisdictions_by_id", {}).values():
            ocdid = jurisdiction["jurisdiction_ocdid"]
            db_record = await database.get_jurisdiction_by_ocdid(ocdid)
            db_updated_at = db_record["updated_at"] if db_record else None
            github_updated_at = jurisdiction.get("updated_at")

            if is_newer(github_updated_at, db_updated_at):
                metadata_path = file_path
                await database.update_jurisdiction(ocdid, state, metadata_path, jurisdiction)
                jurisdiction_ocdids_to_update.add(ocdid)
    
    return jurisdiction_ocdids_to_update

async def sync_people(jurisdiction_ocdids: List[str]):
    for ocdid in jurisdiction_ocdids:
        people_data_path = os.path.join("data", f"{shared.utils.id_utils.jurisdiction_ocdid_to_folder(ocdid)}.yml")
        people_data = await github_service.get_github_file_contents(people_data_path)
        people_data_json = None
        if people_data:
            people_data_json = yaml.safe_load(people_data)
            
        await database.update_people(ocdid, people_data_path, people_data_json)

async def sync_data(states: List[str], jurisdiction_ocdids: Optional[List[str]] = None, sync_all_people: bool = False):
    """
    If jurisdiction_ocdids are provided, sync only those jurisdictions.

    Otherwise, for each state, grab the jurisdiction_ocdids and updated_at timestamps from the database.

    Grab the most recent jurisdiction_metadata.yml file for each state, and compare the updated_at timestamp to the database records to determine which jurisdictions need to be updated.

    If the updated_at timestamp in the GitHub file is more recent than the database record, 
    or if the jurisdiction_ocdid is not in the database, sync that jurisdiction 
    (insert/update jurisdiction record and associated people records).
    """
    if states:
        updated_jurisdiction_ocdids = await sync_jurisdiction_definitions(states)

    if jurisdiction_ocdids:
        await sync_people(jurisdiction_ocdids)

    if not jurisdiction_ocdids and sync_all_people:
        # Grab all jurisdiction
        all_jurisdictions = await database.get_all_jurisdictions()
        await sync_people([jurisdiction["ocdid"] for jurisdiction in all_jurisdictions])

    return updated_jurisdiction_ocdids

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
