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

# Configuration
REPO_URL = "https://github.com/CivicPatch/open-data.git"
REPO_PATH = Path("/app/git_data")
# CRUDDER_DB_URL is expected to be loaded from the environment
CRUDDER_DB_URL = os.getenv("CRUDDER_DB_URL")

# --- FILE PATTERNS ---
DATA_FILES_PATTERN = (
    "data/**/*.yml"  # Matches people files (e.g., data/us/tx/person.yml)
)
JURISDICTION_FILES_PATTERN = (
    "data_source/**/jurisdictions_metadata.yml"  # Fixed: was jurisdictions_metadata.yml
)

# Check for required environment variable before attempting to create pool
if not CRUDDER_DB_URL:
    raise ValueError("CRUDDER_DB_URL environment variable is not set.")


class GitDatabaseSync:
    def __init__(self, pool, repo_url=REPO_URL, repo_path=REPO_PATH):
        self.pool = pool
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

    def get_file_content_at_commit(self, rel_path, commit):
        """Get file content at a specific commit without checking it out"""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_path), "show", f"{commit}:{rel_path}"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            # File might not exist at this commit (deleted file)
            print(f"Could not read {rel_path} at commit {commit}: {e}")
            return None

    def get_changed_files(self, old_commit, new_commit):
        """Get list of changed files between commits that match our patterns"""
        # Determine the base directory for dynamic path checking
        people_base_dir = Path(DATA_FILES_PATTERN).parts[0] + os.sep
        jurisdiction_base_dir = Path(JURISDICTION_FILES_PATTERN).parts[0] + os.sep

        if not old_commit:
            # First sync - use rglob with the patterns
            print(
                f"First sync - processing files matching {DATA_FILES_PATTERN} and {JURISDICTION_FILES_PATTERN}..."
            )
            files = []
            files.extend(list(self.repo_path.rglob(DATA_FILES_PATTERN)))
            files.extend(list(self.repo_path.rglob(JURISDICTION_FILES_PATTERN)))
            return files

        # Get diff between commits - NO CHECKOUT NEEDED
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
            is_people_file = path.startswith(people_base_dir) and Path(path).suffix in [
                ".yml",
                ".yaml",
            ]

            # Filter for JURISDICTION files (dynamic base dir and specific filename)
            is_jurisdiction_file = path.startswith(
                jurisdiction_base_dir
            ) and path.endswith("jurisdictions_metadata.yml")

            if is_people_file or is_jurisdiction_file:
                files.append(full_path)

        return files

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
                content = self.get_file_content_at_commit(rel_path, commit_hash)
                if content is None:
                    return False
                data = yaml.safe_load(content)
            else:
                # Fallback for first sync when files exist on filesystem
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
                content = self.get_file_content_at_commit(rel_path, commit_hash)
                if content is None:
                    return False
                data = yaml.safe_load(content)
            else:
                # Fallback for first sync when files exist on filesystem
                with open(file_path, "r") as f:
                    data = yaml.safe_load(f)
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
                        jurisdiction_id = record.get("jurisdiction_id")
                        jurisdiction_ocdid_slug = record.get("jurisdiction_ocdid_slug")
                        data = record.get("jurisdiction")
                        data["updated_at"] = record.get("updated_at")

                        if not jurisdiction_id:
                            print(
                                f"  Warning: Skipping record in {file_path}. 'id' key not found."
                            )
                            continue

                        values_list.append(
                            (
                                jurisdiction_id,
                                jurisdiction_ocdid_slug,
                                state_abbreviation,
                                rel_path,
                                json.dumps(data),
                                commit_hash,
                            )
                        )

                    if not values_list:
                        return False

                    query = """
                    INSERT INTO jurisdictions (jurisdiction_ocdid, jurisdiction_ocdid_slug, state, file_path, data, updated_at, git_commit)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    ON CONFLICT (jurisdiction_ocdid)
                    DO UPDATE SET
                        jurisdiction_ocdid_slug = EXCLUDED.jurisdiction_ocdid_slug,
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

            # Try to log the failure
            try:
                async with self.pool.connection() as conn:
                    await conn.execute(
                        """
                        INSERT INTO sync_log (git_commit, duration_seconds, status, error)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            new_commit if "new_commit" in locals() else None,
                            duration,
                            "failed",
                            str(e),
                        ),
                    )
                    await conn.commit()
            except:
                pass  # Don't fail if logging fails

async def main():
    syncer = GitDatabaseSync(REPO_URL, REPO_PATH)
    await syncer.sync()


if __name__ == "__main__":
    asyncio.run(main())
