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


class GitDatabaseSync:
    def __init__(self, pool, config=CONFIG):
        self.pool = pool
        self.config = config
        self.repo_url = config["REPO_URL"]
        self.repo_path = Path(config["REPO_PATH"])
        self.data_files_patterns = config["DATA_FILES_PATTERNS"]
        self.jurisdiction_files_pattern = config["JURISDICTION_FILES_PATTERN"]
        self.map_files_pattern = config["MAP_FILES_PATTERN"]

        # Extract subdirs from patterns like "data/*/local/*.yml"
        self.people_subdirs = []
        for pattern in self.data_files_patterns:
            m = re.match(r"data/\*/([^/]+)/\*\.yml", pattern)
            if m:
                self.people_subdirs.append(m.group(1))

    async def is_valid_git_repo(self):
        return await aiofiles.os.path.exists(str(self.repo_path / ".git"))

    async def clone_or_pull(self):
        if await aiofiles.os.path.exists(str(self.repo_path)):
            if await self.is_valid_git_repo():
                print("Fetching latest changes from existing repository...")
                await self._run_git(["fetch", "origin"])
                await self._run_git(["reset", "--hard", "origin/main"])
                return "fetched"
            else:
                print("Repository directory is invalid. Removing and re-cloning...")
                await self._rmtree(self.repo_path)
        print(f"Cloning repository from {self.repo_url}...")
        await self._run_cmd([
            "git", "clone", 
            "--single-branch", "--branch", "main",
            self.repo_url, 
            str(self.repo_path)
        ])
        return "cloned"

    async def _run_git(self, args):
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(self.repo_path), *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(args)}\n{stderr.decode()}")

    async def _run_cmd(self, args):
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(args)}\n{stderr.decode()}")

    async def _rmtree(self, path):
        # Run blocking rmtree in a thread
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, shutil.rmtree, path)

    async def get_current_commit(self):
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(self.repo_path), "rev-parse", "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Git rev-parse failed: {stderr.decode()}")
        return stdout.decode().strip()

    async def get_file_content_at_commit(self, rel_path, commit):
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.repo_path), "show", f"{commit}:{rel_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                print(f"Could not read {rel_path} at commit {commit}: {stderr.decode()}")
                return None
            return stdout.decode()
        except Exception as e:
            print(f"Could not read {rel_path} at commit {commit}: {e}")
            return None

    async def get_last_synced_commit(self):
        """Get the last commit that was synced. Assumes sync_log table exists."""
        async with self.pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT git_commit FROM sync_log ORDER BY sync_time DESC LIMIT 1"
            )
            result = await cur.fetchone()
            return result[0] if result else None

    async def update_file_in_db(self, file_path, commit_hash, use_git_show=True):
        """Update a single PEOPLE file in the database (into the 'people' table)"""
        try:
            # Read content from git history or filesystem
            if use_git_show:
                rel_path = str(file_path.relative_to(self.repo_path))
                content = await self.get_file_content_at_commit(rel_path, commit_hash)
                if content is None:
                    return False
                data = yaml.safe_load(content)
            else:
                # Fallback for first sync when files exist on filesystem
                async with aiofiles.open(file_path, "r") as f:
                    content = await f.read()
                    data = yaml.safe_load(content)
                rel_path = str(file_path.relative_to(self.repo_path))

            if not isinstance(data, list) or not data:
                print(f"Skipping {file_path}: YAML content is not a list or is empty.")
                return False

            person = data[0]
            jurisdiction_ocdid = person.get("jurisdiction_ocdid")

            if not jurisdiction_ocdid:
                print(f"Skipping {file_path}: 'jurisdiction_ocdid' missing in data.")
                return False

            async with self.pool.connection() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO people (jurisdiction_ocdid, file_path, data, updated_at, git_commit)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s)
                        ON CONFLICT (jurisdiction_ocdid)
                        DO UPDATE SET
                            data = EXCLUDED.data,
                            updated_at = CURRENT_TIMESTAMP,
                            git_commit = EXCLUDED.git_commit
                        """,
                        (jurisdiction_ocdid, rel_path, json.dumps(data), commit_hash),
                    )

            return True

        except Exception as e:
            print(f"Error updating PEOPLE file {file_path}: {e}")
            return False

    async def update_jurisdiction_in_db(
        self, file_path, commit_hash, use_git_show=True
    ):
        """Update a single JURISDICTION file in the database (into the 'jurisdictions' table)"""
        try:
            # Read content from git history or filesystem
            if use_git_show:
                rel_path = str(file_path.relative_to(self.repo_path))
                content = await self.get_file_content_at_commit(rel_path, commit_hash)
                if content is None:
                    return False
                data = yaml.safe_load(content)
            else:
                # Fallback for first sync when files exist on filesystem
                async with aiofiles.open(file_path, "r") as f:
                    content = await f.read()
                    data = yaml.safe_load(content)
                rel_path = str(file_path.relative_to(self.repo_path))

            jurisdictions_by_id = data.get("jurisdictions_by_id", {})
            jurisdictions = list(jurisdictions_by_id.values())

            if not isinstance(jurisdictions, list) or not jurisdictions:
                print(f"Skipping {file_path}: YAML content is not a list or is empty.")
                return False

            # Extract state abbreviation from path
            path_parts = rel_path.split(os.sep)
            state_abbreviation = path_parts[1]

            async with self.pool.connection() as conn, conn.cursor() as cur:
                async with conn.transaction():
                    values_list = []

                    # Prepare data for all records in a single list of tuples
                    for record in jurisdictions:
                        jurisdiction_ocdid = record.get("jurisdiction_ocdid")
                        data = record.get("jurisdiction")
                        data["updated_at"] = record.get("updated_at")

                        if not jurisdiction_ocdid:
                            print(
                                f"  Warning: Skipping record in {file_path}. 'id' key not found."
                            )
                            continue

                        values_list.append(
                            (
                                jurisdiction_ocdid,
                                state_abbreviation,
                                rel_path,
                                json.dumps(data),
                                commit_hash,
                            )
                        )

                    if not values_list:
                        return False

                    query = """
                    INSERT INTO jurisdictions (jurisdiction_ocdid, state, file_path, data, updated_at, git_commit)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    ON CONFLICT (jurisdiction_ocdid)
                    DO UPDATE SET
                        data = EXCLUDED.data,
                        updated_at = CURRENT_TIMESTAMP,
                        git_commit = EXCLUDED.git_commit;
                    """

                    await cur.executemany(query, values_list)

                    successful_updates = len(values_list)
                    print(
                        f"  Successfully processed {successful_updates} jurisdiction records from {rel_path} in bulk."
                    )

                    return successful_updates > 0

        except Exception as e:
            print(f"Error updating JURISDICTION file {file_path}: {e}")
            return False

    async def update_geo_in_db(self, file_path, commit_hash, use_git_show=True):
        """Update a GEOJSON file into the geo table. Handles FeatureCollection and Feature objects."""
        # Read content from git history or filesystem
        if use_git_show:
            rel_path = str(file_path.relative_to(self.repo_path))
            content = await self.get_file_content_at_commit(rel_path, commit_hash)
            if content is None:
                return False
            data = json.loads(content)
        else:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                data = json.loads(content)
            rel_path = str(file_path.relative_to(self.repo_path))

        # Normalize to list of features
        features = []
        if data.get("type") == "FeatureCollection":
            features = data.get("features", [])
        elif data.get("type") == "Feature":
            features = [data]
        else:
            # Some geojson files may be a single geometry + properties
            print(f"Skipping {file_path}: not a Feature/FeatureCollection.")
            return False

        if not features:
            print(f"Skipping {file_path}: no features found.")
            return False

        values_list = []
        for feat in features:
            props = feat.get("properties", {}) or {}
            geoid = props.get("geoid") or props.get("GEOID")
            # geometry as GeoJSON text
            geom_obj = feat.get("geometry")
            if not geoid or not geom_obj:
                print(
                    f"  Warning: Skipping feature without geoid or geometry in {file_path}."
                )
                continue

            statefp = props.get("STATEFP")
            name = props.get("NAME")
            funcstat = props.get("FUNCSTAT")
            typ = props.get("type")

            meta = props

            values_list.append(
                (
                    geoid,
                    json.dumps(geom_obj),
                    json.dumps(meta),
                    statefp,
                    name,
                    funcstat,
                    typ,
                    rel_path,
                    commit_hash,
                )
            )

        if not values_list:
            return False

        # Upsert all features
        async with self.pool.connection() as conn, conn.cursor() as cur:
            async with conn.transaction():
                query = """
                INSERT INTO geo (geoid, geom, meta, statefp, name, funcstat, type, file_path, git_commit)
                VALUES (%s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (geoid)
                DO UPDATE SET
                    geom = EXCLUDED.geom,
                    meta = EXCLUDED.meta,
                    statefp = EXCLUDED.statefp,
                    name = EXCLUDED.name,
                    funcstat = EXCLUDED.funcstat,
                    type = EXCLUDED.type,
                    file_path = EXCLUDED.file_path,
                    git_commit = EXCLUDED.git_commit,
                    updated_at = CURRENT_TIMESTAMP;
                """

                await cur.executemany(query, values_list)

        print(
            f"  Successfully processed {len(values_list)} geo features from {rel_path} in bulk."
        )

        return commit_hash

    async def get_changed_files(self, old_commit, new_commit):
        """
        Returns a list of Path objects for files changed between old_commit and new_commit.
        If old_commit is None, returns all files matching the patterns.
        """
        if old_commit:
            # Use git diff to get changed files
            proc = await asyncio.create_subprocess_exec(
                "git", "-C", str(self.repo_path), "diff", "--name-only", old_commit, new_commit,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"Git diff failed: {stderr.decode()}")
            files = stdout.decode().splitlines()
        else:
            # First sync: return all files matching patterns
            files = []
            for pattern in self.data_files_patterns + [self.jurisdiction_files_pattern, self.map_files_pattern]:
                files.extend([str(p) for p in self.repo_path.glob(pattern)])

        # Filter files to only those matching your patterns
        matched_files = []
        patterns = self.data_files_patterns + [self.jurisdiction_files_pattern, self.map_files_pattern]
        for file in files:
            for pattern in patterns:
                # Convert glob to fnmatch pattern
                pat = pattern.replace("**/", "**").replace("*", "*")
                if fnmatch.fnmatch(file, pat) or fnmatch.fnmatch(str(file), pat):
                    matched_files.append(self.repo_path / file if not file.startswith(str(self.repo_path)) else Path(file))
                    break

        # Remove duplicates and ensure Path objects
        unique_files = list({str(f): f for f in matched_files}.values())
        return unique_files

    async def sync(self):
        """Main sync process"""
        print(f"=== Starting sync at {datetime.now()} ===")
        start_time = datetime.now()

        # Ensure pool is open
        await self.pool.open()

        try:
            # Get last synced commit
            old_commit = await self.get_last_synced_commit()

            # Clone or pull repo (synchronous git operations)
            clone_status = await self.clone_or_pull()

            # No need for additional pull since clone_or_pull handles both cases

            # Get current commit
            new_commit = await self.get_current_commit()

            if old_commit == new_commit:
                print(
                    "No new changes detected in the repository. Database is up to date."
                )
                return

            print(f"Syncing from {old_commit or 'initial'} to {new_commit}")

            # Get changed files (will filter for both people and jurisdiction files)
            changed_files = await self.get_changed_files(old_commit, new_commit)
            print(f"Found {len(changed_files)} changed files")

            # Update database
            updated_count = 0
            failed_files = []

            # Determine if we need to use git show (only if not first sync)
            use_git_show = old_commit is not None

            for file_path in changed_files:
                updated = False

                try:
                    # Dispatch based on filename/path structure
                    if file_path.name == "jurisdictions_metadata.yml":
                        updated = await self.update_jurisdiction_in_db(
                            file_path, new_commit, use_git_show
                        )
                    elif file_path.suffix == ".geojson" or ".maps" in str(file_path):
                        updated = await self.update_geo_in_db(
                            file_path, new_commit, use_git_show
                        )
                    else:
                        updated = await self.update_file_in_db(
                            file_path, new_commit, use_git_show
                        )

                    if updated:
                        updated_count += 1
                        if updated_count % 100 == 0:
                            print(f"Updated {updated_count} files...")

                except Exception as e:
                    failed_files.append((str(file_path), str(e)))
                    print(f"Failed to process {file_path}: {e}")

            duration = (datetime.now() - start_time).total_seconds()

            # Log sync
            async with self.pool.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO sync_log (files_updated, git_commit, sync_time)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    """,
                    (
                        updated_count,
                        new_commit,
                    ),
                )
                await conn.commit()

            print(
                f"=== Sync complete: {updated_count} files updated in {duration:.2f}s ==="
            )

            if failed_files:
                print(f"WARNING: {len(failed_files)} files failed to sync:")
                for path, error in failed_files[:10]:  # Show first 10 errors
                    print(f"  - {path}: {error}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"FATAL SYNC ERROR: {e}")

import aiofiles
import yaml

async def sync_jurisdictions(jurisdiction_ocdids, syncer):
    """
    For each jurisdiction OCDID, find the relevant jurisdiction_metadata.yml and data.yml,
    then bulk insert jurisdiction and people records.
    """
    states = list(set([
        ocdid.split("/")[2].split(":")[1]
        for ocdid in jurisdiction_ocdids
    ]))
    state_metadata_files = {}
    for state in states:
        # Find jurisdiction_metadata.yml for each state
        metadata_files = list(REPO_PATH.glob(f"data/{state}/local/jurisdictions_metadata.yml"))
        state_metadata_files[state] = metadata_files[0] if metadata_files else None

    for jurisdiction_ocdid in jurisdiction_ocdids:
        jurisdiction_state = jurisdiction_ocdid.split("/")[2].split(":")[1]
        metadata_path = state_metadata_files.get(jurisdiction_state)
        if metadata_path is None:
            print(f"No jurisdiction_metadata.yml found for state {jurisdiction_state}")
            continue

        # Find people data file for this jurisdiction
        people_data_path = None
        # Example: data/{state}/local/data.yml or similar pattern
        possible_people_files = list(REPO_PATH.glob(f"data/{jurisdiction_state}/local/*.yml"))
        for pfile in possible_people_files:
            async with aiofiles.open(pfile, "r") as f:
                content = await f.read()
                data = yaml.safe_load(content)
                # Check if this file contains people for the jurisdiction_ocdid
                if isinstance(data, list) and any(person.get("jurisdiction_ocdid") == jurisdiction_ocdid for person in data):
                    people_data_path = pfile
                    break

        await process_jurisdiction(metadata_path, people_data_path, jurisdiction_ocdid, syncer)

async def process_jurisdiction(metadata_path, people_data_path, jurisdiction_ocdid, syncer):
    """
    Insert jurisdiction and people records for a single jurisdiction_ocdid.
    """
    # Insert jurisdiction record(s)
    if metadata_path:
        async with aiofiles.open(metadata_path, "r") as f:
            content = await f.read()
            data = yaml.safe_load(content)
        commit_hash = await syncer.get_current_commit()
        await syncer.update_jurisdiction_in_db(metadata_path, commit_hash, use_git_show=False)

    # Insert people record(s)
    if people_data_path:
        async with aiofiles.open(people_data_path, "r") as f:
            content = await f.read()
            data = yaml.safe_load(content)
        commit_hash = await syncer.get_current_commit()
        await syncer.update_file_in_db(people_data_path, commit_hash, use_git_show=False)

async def main():

    syncer = GitDatabaseSync(None, config=CONFIG)
    await syncer.sync()


if __name__ == "__main__":
    asyncio.run(main())
