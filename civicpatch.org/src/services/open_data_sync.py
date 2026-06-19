import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Tuple

import database.jurisdictions as jurisdictions_db
import database.people as people_db
import database.synced_files as synced_files_db
import environment
import lib.github.api as github_service
import shared.utils.id_utils
import yaml
from core.sync_paths import classify_path
from core.tree_diff import TreeDiff, diff_tree
from database.synced_files import get_synced_file_shas

logger = logging.getLogger(__name__)

_MAX_FILES_PER_RUN = (
    500  # cap GitHub fetches per run; the backlog drains over later runs
)


def get_current_tree(
    tree: github_service.RepoTree,
) -> Tuple[dict[str, str], dict[str, str]]:
    jurisdictions = {}
    people = {}

    for candidate_path, candidate_sha in tree.entries.items():
        path_type = classify_path(candidate_path)
        if path_type is None:
            continue
        elif path_type == "jurisdictions":
            jurisdictions[candidate_path] = candidate_sha
        elif path_type == "people":
            people[candidate_path] = candidate_sha

    return jurisdictions, people


def get_stored_tree(
    synced_files: dict[str, str],
) -> Tuple[dict[str, str], dict[str, str]]:
    jurisdictions = {}
    people = {}

    for candidate_path, candidate_sha in synced_files.items():
        path_type = classify_path(candidate_path)
        if path_type is None:
            continue
        elif path_type == "jurisdictions":
            jurisdictions[candidate_path] = candidate_sha
        elif path_type == "people":
            people[candidate_path] = candidate_sha

    return jurisdictions, people


# path -> sha: list[path]
async def sync_jurisdictions(diffs: TreeDiff) -> list[str]:
    semaphore = asyncio.Semaphore(10)
    now = datetime.now(timezone.utc)

    async def _fetch(path):
        async with semaphore:
            content = await github_service.get_github_file_contents(path)
        return path, content

    rows, synced, state_keep = [], [], {}
    for path, content in await asyncio.gather(*[_fetch(p) for p in diffs.changed]):
        if content is None:
            logger.warning("od_sync: no content for %s; skipping this run", path)
            continue
        entries = (yaml.safe_load(content) or {}).get("jurisdictions", [])
        state = path.split("/")[1]
        rows.extend(jurisdictions_db.jurisdiction_rows(entries, state, "local", now))
        state_keep[state] = [
            e["id"] for e in entries if e.get("id")
        ]  # the authoritative list
        synced.append(path)
    await jurisdictions_db.bulk_update_jurisdictions(rows)

    # within-list removal: a jurisdiction no longer in a synced state's list
    for state, keep in state_keep.items():
        await jurisdictions_db.deactivate_jurisdictions_not_in(state, keep)

    return synced


async def sync_people(diffs: TreeDiff) -> list[str]:
    semaphore = asyncio.Semaphore(10)

    async def _fetch(path):
        async with semaphore:
            content = await github_service.get_github_file_contents(path)
        return path, content

    people, synced = [], []
    for path, content in await asyncio.gather(*[_fetch(p) for p in diffs.changed]):
        if content is None:
            logger.warning("od_sync: no content for %s; skipping this run", path)
            continue
        people.extend(yaml.safe_load(content) or [])
        synced.append(path)
    logger.debug("Prepared %d people for bulk update.", len(people))
    await people_db.bulk_update_people(people)
    return synced


async def sync_all():
    logger.info("Starting bulk sync")

    env = environment.get_env_vars()
    tree = await github_service.get_tree(env["OPEN_DATA_REPO_URL"])

    current_jurisdictions, current_people_by_jurisdictions = get_current_tree(tree)

    synced_files = await get_synced_file_shas()
    stored_jurisdictions, stored_people_by_jurisdicitons = get_stored_tree(synced_files)

    jurisdiction_diffs = diff_tree(current_jurisdictions, stored_jurisdictions)
    people_diffs = diff_tree(
        current_people_by_jurisdictions, stored_people_by_jurisdicitons
    )

    # truncation guard: an incomplete tree must not drive deletions
    if tree.truncated:
        logger.warning("od_sync: tree truncated; skipping the deletion pass this run")
        jurisdiction_diffs = TreeDiff(changed=jurisdiction_diffs.changed, deleted=[])
        people_diffs = TreeDiff(changed=people_diffs.changed, deleted=[])

    # cap GitHub load per run (jurisdictions are few, so cap the people backlog);
    # deferred people stay "changed" next run since their cursors aren't advanced
    if len(people_diffs.changed) > _MAX_FILES_PER_RUN:
        logger.info(
            "od_sync: capping at %d people this run; %d deferred to next run",
            _MAX_FILES_PER_RUN,
            len(people_diffs.changed) - _MAX_FILES_PER_RUN,
        )
        people_diffs = TreeDiff(
            changed=people_diffs.changed[:_MAX_FILES_PER_RUN],
            deleted=people_diffs.deleted,
        )

    # jurisdictions before people: a new jurisdiction must exist before its people rows
    synced_jurisdictions = await sync_jurisdictions(jurisdiction_diffs)
    synced_people = await sync_people(people_diffs)

    # SHA last, only for files that synced — a transient miss retries next run
    for path in synced_jurisdictions:
        await synced_files_db.upsert_synced_file(path, current_jurisdictions[path])
    for path in synced_people:
        await synced_files_db.upsert_synced_file(
            path, current_people_by_jurisdictions[path]
        )
    # drop cursors for files that left the tree
    for path in jurisdiction_diffs.deleted + people_diffs.deleted:
        await synced_files_db.delete_synced_files(paths=[path])


# --- Targeted refresh (specific jurisdictions) — used by publish_side_effects (post-merge),
#     the /od_sync endpoint with ids, and seed_dev_prs. They reuse the per-kind functions via a
#     one-off TreeDiff (no cursor advancement — the bulk run owns the cursors).


def _people_path(jurisdiction_ocdid: str) -> str:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return os.path.join("data", f"{folder}.yml")


async def sync_people_by_ocdids(jurisdiction_ocdids):
    paths = [_people_path(o) for o in jurisdiction_ocdids]
    await sync_people(TreeDiff(changed=paths, deleted=[]))


async def sync_jurisdictions_by_ocdids(jurisdiction_ocdids):
    states = {
        shared.utils.id_utils.parse_jurisdiction_ocdid(o).state
        for o in jurisdiction_ocdids
    }
    paths = [
        os.path.join("data_source", s, "local", "jurisdictions.yml") for s in states
    ]
    await sync_jurisdictions(TreeDiff(changed=paths, deleted=[]))


async def sync_by_ocdids(jurisdiction_ocdids: list[str]):
    logger.info(f"Targeted sync for OCDIDs: {jurisdiction_ocdids}")
    await sync_jurisdictions_by_ocdids(jurisdiction_ocdids)
    await sync_people_by_ocdids(jurisdiction_ocdids)
