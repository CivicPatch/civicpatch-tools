#!/usr/bin/env python3
"""
Daily sync script to update PostgreSQL database with changed files from Git repo
Compatible with existing psycopg_pool AsyncConnectionPool setup
"""

import asyncio
import json
import os
import shutil  # NEW: Added for robust directory removal
import subprocess
from datetime import datetime
from pathlib import Path

import yaml
from psycopg_pool import AsyncConnectionPool

# Configuration
REPO_URL = "https://github.com/CivicPatch/open-data.git"
# CRITICAL CHANGE: Using an absolute path inside the container for robustness,
# ensuring the cloned data goes into /app/data, which acts as the temporary folder.
REPO_PATH = Path("/app/git_data")
# CRUDDER_DB_URL is expected to be loaded from the environment
CRUDDER_DB_URL = os.getenv("CRUDDER_DB_URL")
DATA_FILES_PATTERN = "data/**/*.yml"  # Adjust to match your file pattern

# Check for required environment variable before attempting to create pool
if not CRUDDER_DB_URL:
    raise ValueError("CRUDDER_DB_URL environment variable is not set.")

# Create a separate pool for this script (not shared with web app)
# This pool will be opened/closed within the script's lifecycle
sync_pool = AsyncConnectionPool(CRUDDER_DB_URL, open=False)


class GitDatabaseSync:
    def __init__(self, repo_url = REPO_URL, repo_path = REPO_PATH):
        self.repo_url = repo_url
        # CRITICAL CHANGE: Ensure repo_path is treated as a Path object
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
        # Clone automatically pulls down the 'main' branch content
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
        """Get list of changed files between commits"""

        # --- REMOVED IGNORED_FILES definition ---

        if not old_commit:
            # First sync - get all files using the specific pattern
            print("First sync - processing files matching data/**/*.yml...")
            # We use the pattern 'data/**/*.yml' which matches files within the 'data' subdirectory
            # of the cloned repo. This achieves the user's goal of specific pattern matching.
            return [f for f in self.repo_path.rglob("data/**/*.yml")]

        # Ensure we are checking the differences against the actual working tree
        # by explicitly checking out the new commit before diffing against the old one.
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
        changed_paths = [p for p in changed_paths if p]  # Remove empty strings

        # Filter for yml files and convert to full paths
        files = []
        for path in changed_paths:
            full_path = self.repo_path / path

            # Filter the paths returned by git diff to match the specific pattern:
            # path must start with 'data/' and end with a YAML extension.
            is_data_file = path.startswith("data/") and full_path.suffix in [
                ".yml",
                ".yaml",
            ]

            if full_path.exists() and is_data_file:
                files.append(full_path)

        return files

    async def get_last_synced_commit(self):
        """Get the last commit that was synced"""
        try:
            async with sync_pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT git_commit FROM sync_log ORDER BY sync_time DESC LIMIT 1"
                )
                result = await cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            # Table might not exist yet on first run
            print(f"Warning: Could not fetch last commit (Table error?): {e}")
            return None

    async def update_file_in_db(self, file_path, commit_hash):
        """Update a single file in the database"""
        try:
            with open(file_path, "r") as f:
                # Parse YAML file
                data = yaml.safe_load(f)

            # Store relative path from repo root
            rel_path = str(file_path.relative_to(self.repo_path))

            # Assuming 'data' is a list and we only need the jurisdiction_id from the first element
            if not isinstance(data, list) or not data:
                print(f"Skipping {file_path}: YAML content is not a list or is empty.")
                return False

            person = data[0]
            jurisdiction_ocdid = person.get("jurisdiction_id")

            # The original query was missing the 'data' field in the VALUES list. Fixed below.
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
                await (
                    conn.commit()
                )  # Ensure commit is called if using connection context manager

            return True
        except Exception as e:
            print(f"Error updating {file_path}: {e}")
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

            # The current branch is 'main' if it was cloned or a valid repo existed.
            # Run pull for the latest data, which is now safe since we ensured it's a valid repo.
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

            # Get changed files
            changed_files = self.get_changed_files(old_commit, new_commit)
            print(f"Found {len(changed_files)} changed files")

            # Update database
            updated_count = 0
            for file_path in changed_files:
                if await self.update_file_in_db(file_path, new_commit):
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
