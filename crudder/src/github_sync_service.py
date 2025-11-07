#!/usr/bin/env python3
"""
Daily sync script to update PostgreSQL database with changed files from Git repo
Compatible with existing psycopg_pool AsyncConnectionPool setup
"""

import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import yaml
from psycopg_pool import AsyncConnectionPool

# Configuration
REPO_URL = "https://github.com/CivicPatch/open-data.git"
REPO_PATH = Path("/app/git_data")
# CRUDDER_DB_URL is expected to be loaded from the environment
CRUDDER_DB_URL = os.getenv("CRUDDER_DB_URL")

# --- FILE PATTERNS ---
DATA_FILES_PATTERN = "data/**/*.yml"  # Matches people files (e.g., data/us/tx/person.yml)
JURISDICTION_FILES_PATTERN = "data_source/**/jurisdictions.yml"  # Matches jurisdiction files

# Check for required environment variable before attempting to create pool
if not CRUDDER_DB_URL:
    raise ValueError("CRUDDER_DB_URL environment variable is not set.")

# Create a separate pool for this script (not shared with web app)
sync_pool = AsyncConnectionPool(CRUDDER_DB_URL, open=False)


class GitDatabaseSync:
    def __init__(self, repo_url=REPO_URL, repo_path=REPO_PATH):
        self.repo_url = repo_url
        self.repo_path = Path(repo_path)

    def is_valid_git_repo(self):
        """Checks if the directory contains a valid .git folder"""
        return (self.repo_path / ".git").is_dir()

    def clone_or_pull(self):
        """Clone repo if it doesn't exist or is invalid, otherwise fetch latest"""
        if self.repo_path.exists():
            if self.is_valid_git_repo():
                print("Fetching latest changes from existing repository...")
                # Ensure we are in the directory for fetch
                subprocess.run(
                    ["git", "-C", str(self.repo_path), "fetch", "origin"], check=True
                )
                return "fetched"
            else:
                # Directory exists but is not a valid repo (e.g., partial clone)
                print("Repository directory is invalid. Removing and re-cloning...")
                shutil.rmtree(self.repo_path)

        # If directory didn't exist, or was just removed:
        print(f"Cloning repository from {self.repo_url}...")
        subprocess.run(["git", "clone", self.repo_url, str(self.repo_path)], check=True)
        return "cloned"

    def get_current_commit(self):
        """Get current commit hash"""
        result = subprocess.run(
            ["git", "-C", str(self.repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def get_changed_files(self, old_commit, new_commit):
        """Get list of changed files between commits that match our patterns"""

        # Determine the base directory for dynamic path checking
        people_base_dir = Path(DATA_FILES_PATTERN).parts[0] + os.sep
        jurisdiction_base_dir = Path(JURISDICTION_FILES_PATTERN).parts[0] + os.sep

        if not old_commit:
            # First sync - use rglob with the patterns
            print(f"First sync - processing files matching {DATA_FILES_PATTERN} and {JURISDICTION_FILES_PATTERN}...")

            files = []
            files.extend(list(self.repo_path.rglob(DATA_FILES_PATTERN)))
            files.extend(list(self.repo_path.rglob(JURISDICTION_FILES_PATTERN)))
            return files

        # Ensure we are checking the differences against the actual working tree
        subprocess.run(
            ["git", "-C", str(self.repo_path), "checkout", new_commit], check=True
        )

        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.repo_path),
                "diff",
                "--name-only",
                old_commit,
                new_commit,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        changed_paths = result.stdout.strip().split("\n")
        changed_paths = [p for p in changed_paths if p]

        # Filter for files matching either pattern
        files = []
        for path in changed_paths:
            full_path = self.repo_path / path

            # Filter for PEOPLE files (dynamic base dir and yml suffix)
            is_people_file = path.startswith(people_base_dir) and full_path.suffix in [
                ".yml",
                ".yaml",
            ]

            # Filter for JURISDICTION files (dynamic base dir and specific filename)
            is_jurisdiction_file = path.startswith(jurisdiction_base_dir) and path.endswith("jurisdictions.yml")

            if full_path.exists() and (is_people_file or is_jurisdiction_file):
                files.append(full_path)

        return files

    async def get_last_synced_commit(self):
        """Get the last commit that was synced. Assumes sync_log table exists."""
        # Removed try...except block as per user request (schema guaranteed to exist)
        async with sync_pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT git_commit FROM sync_log ORDER BY sync_time DESC LIMIT 1"
            )
            result = await cur.fetchone()
            # If table exists but is empty, result is None, which is fine
            return result[0] if result else None

    async def update_file_in_db(self, file_path, commit_hash):
        """Update a single PEOPLE file in the database (into the 'people' table)"""
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)

            rel_path = str(file_path.relative_to(self.repo_path))

            if not isinstance(data, list) or not data:
                print(f"Skipping {file_path}: YAML content is not a list or is empty.")
                return False

            person = data[0]
            jurisdiction_ocdid = person.get("jurisdiction_id")

            if not jurisdiction_ocdid:
                 print(f"Skipping {file_path}: 'jurisdiction_id' missing in data.")
                 return False

            async with sync_pool.connection() as conn:
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
                await conn.commit()

            return True
        except Exception as e:
            print(f"Error updating PEOPLE file {file_path}: {e}")
            return False

    async def update_jurisdiction_in_db(self, file_path, commit_hash):
        """Update a single JURISDICTION file in the database (into the 'jurisdictions' table)"""
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)

            jurisdictions = data.get("jurisdictions")
            if not isinstance(jurisdictions, list) or not jurisdictions:
                print(f"Skipping {file_path}: YAML content is not a list or is empty.")
                return False

            # --- JURISDICTION ID EXTRACTION & LOGIC ---
            rel_path = str(file_path.relative_to(self.repo_path))

            # The path will be 'data_source/wa/jurisdictions.yml'. We want 'wa'.
            # We convert the Path object back to a string and split by the OS separator
            path_parts = rel_path.split(os.sep)
            # path_parts[0] is 'data_source', path_parts[1] is the state code
            state_abbreviation = path_parts[1]
            # --- Inside update_jurisdiction_in_db ---

            # ... (YAML loading and path preparation remains the same)

            async with sync_pool.connection() as conn, conn.cursor() as cur:

                values_list = []

                # Prepare data for all records in a single list of tuples
                for record in jurisdictions:
                    jurisdiction_id = record.get("id")
                    if not jurisdiction_id:
                        print(f"  Warning: Skipping record in {file_path}. 'id' key not found.")
                        continue

                    values_list.append(
                        (
                            jurisdiction_id,
                            state_abbreviation,
                            rel_path,
                            json.dumps(record),
                            commit_hash
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

                # Use executemany for bulk operation
                # Note: Psycopg's executemany is highly optimized in modern versions.
                await cur.executemany(query, values_list)

                await conn.commit()

                successful_updates = len(values_list)
                print(f"  Successfully processed {successful_updates} jurisdiction records from {rel_path} in bulk.")

                return successful_updates > 0
            return successful_updates > 0
        except Exception as e:
            print(f"Error updating JURISDICTION file {file_path}: {e}")
            return False

    async def sync(self):
        """Main sync process"""
        print(f"=== Starting sync at {datetime.now()} ===")

        # Ensure pool is open
        await sync_pool.open()

        try:
            # Get last synced commit
            old_commit = await self.get_last_synced_commit()

            # Clone or pull repo (synchronous git operations)
            clone_status = self.clone_or_pull()

            if clone_status != "cloned":
                print("Pulling latest changes from main branch...")
                subprocess.run(
                    ["git", "-C", str(self.repo_path), "pull", "origin", "main"],
                    check=True,
                )

            # Get current commit
            new_commit = self.get_current_commit()

            if old_commit == new_commit:
                print(
                    "No new changes detected in the repository. Database is up to date."
                )
                return

            print(f"Syncing from {old_commit or 'initial'} to {new_commit}")

            # Get changed files (will filter for both people and jurisdiction files)
            changed_files = self.get_changed_files(old_commit, new_commit)
            print(f"Found {len(changed_files)} changed files")

            # Update database
            updated_count = 0
            for file_path in changed_files:
                updated = False

                # Dispatch based on filename/path structure
                if file_path.name == "jurisdictions.yml":
                    # Dispatch to jurisdiction update method
                    updated = await self.update_jurisdiction_in_db(file_path, new_commit)
                else:
                    # Dispatch to people update method (assumes all other filtered files are people data)
                    updated = await self.update_file_in_db(file_path, new_commit)

                if updated:
                    updated_count += 1
                    if updated_count % 100 == 0:
                        print(f"Updated {updated_count} files...")

            # Log sync
            async with sync_pool.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO sync_log (files_updated, git_commit)
                    VALUES (%s, %s)
                    """,
                    (updated_count, new_commit),
                )
                await conn.commit()

            print(f"=== Sync complete: {updated_count} files updated ===")
        except Exception as e:
            print(f"FATAL SYNC ERROR: {e}")
        finally:
            await sync_pool.close()


async def main():
    syncer = GitDatabaseSync(REPO_URL, REPO_PATH)
    await syncer.sync()


if __name__ == "__main__":
    asyncio.run(main())
