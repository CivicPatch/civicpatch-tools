import asyncio
import logging
from datetime import datetime, timezone

import database.jurisdictions as jurisdictions_db
import database.synced_files as synced_files_db
import environment
import lib.github.api as github_service
import yaml
from core.open_data.paths import (
    SyncFileKind,
    classify_path,
    jurisdiction_path_parts,
    jurisdictions_file_path,
    level_ordered_batches,
)
from core.open_data.tree_diff import TreeDiff, diff_tree
from database.synced_files import get_synced_file_shas

logger = logging.getLogger(__name__)


# Jurisdictions only. The people half went with migration 150: `data/**` is rendered *from*
# the database now, so a cursor over it describes a direction that no longer exists.
def get_current_tree(tree: github_service.RepoTree) -> dict[str, str]:
    return {
        path: sha
        for path, sha in tree.entries.items()
        if classify_path(path) is SyncFileKind.JURISDICTIONS
    }


def get_stored_tree(synced_files: dict[str, str]) -> dict[str, str]:
    return {
        path: sha
        for path, sha in synced_files.items()
        if classify_path(path) is SyncFileKind.JURISDICTIONS
    }


async def _sync_jurisdiction_level(paths: list[str], now, fetch) -> list[str]:
    # Reading state names here is safe because level_ordered_batches runs the state group
    # first: any state file in this same diff is already stored before the levels that
    # embed its display name are built.
    state_names = await jurisdictions_db.get_state_names()

    rows, synced, slice_keep = [], [], {}
    for path, content in await asyncio.gather(*[fetch(p) for p in paths]):
        if content is None:
            logger.warning("od_sync: no content for %s; skipping this run", path)
            continue
        entries = (yaml.safe_load(content) or {}).get("jurisdictions", [])
        state, level = jurisdiction_path_parts(path)
        rows.extend(
            jurisdictions_db.jurisdiction_rows(
                entries, state, level, now, state_names.get(state)
            )
        )
        slice_keep[(state, level)] = [
            e["id"] for e in entries if e.get("id")
        ]  # the authoritative list for this (state, level) file
        synced.append(path)
    await jurisdictions_db.bulk_update_jurisdictions(rows)

    # within-list removal: a jurisdiction no longer in a synced file's (state, level) list
    for (state, level), keep in slice_keep.items():
        await jurisdictions_db.deactivate_jurisdictions_not_in(state, level, keep)

    return synced


# path -> sha: list[path]
async def sync_jurisdictions(diffs: TreeDiff) -> list[str]:
    semaphore = asyncio.Semaphore(10)
    now = datetime.now(timezone.utc)

    async def _fetch(path):
        async with semaphore:
            content = await github_service.get_github_file_contents(path)
        return path, content

    synced = []
    for batch in level_ordered_batches(diffs.changed):
        synced.extend(await _sync_jurisdiction_level(batch, now, _fetch))
    return synced


async def sync_all():
    logger.info("Starting bulk sync")

    env = environment.get_env_vars()
    tree = await github_service.get_tree(env["OPEN_DATA_REPO_URL"])

    current_jurisdictions = get_current_tree(tree)

    synced_files = await get_synced_file_shas()
    stored_jurisdictions = get_stored_tree(synced_files)

    jurisdiction_diffs = diff_tree(current_jurisdictions, stored_jurisdictions)

    # truncation guard: an incomplete tree must not drive deletions
    if tree.truncated:
        logger.warning("od_sync: tree truncated; skipping the deletion pass this run")
        jurisdiction_diffs = TreeDiff(changed=jurisdiction_diffs.changed, deleted=[])

    synced_jurisdictions = await sync_jurisdictions(jurisdiction_diffs)

    # SHA last, only for files that synced — a transient miss retries next run
    for path in synced_jurisdictions:
        await synced_files_db.upsert_synced_file(path, current_jurisdictions[path])
    # drop cursors for files that left the tree
    for path in jurisdiction_diffs.deleted:
        await synced_files_db.delete_synced_files(paths=[path])


# --- Targeted refresh (specific jurisdictions) — used by publish_side_effects (post-merge),
#     the /od_sync endpoint with ids, and seed_dev_prs. They reuse the per-kind functions via a
#     one-off TreeDiff (no cursor advancement — the bulk run owns the cursors).


async def sync_jurisdictions_by_ocdids(jurisdiction_ocdids):
    # The ocdid says which level it is, so a county or state id refreshes its own file
    # rather than the state's local list. sync_jurisdictions orders the batches.
    paths = {jurisdictions_file_path(o) for o in jurisdiction_ocdids}
    await sync_jurisdictions(TreeDiff(changed=sorted(paths), deleted=[]))


async def sync_by_ocdids(jurisdiction_ocdids: list[str]):
    logger.info(f"Targeted sync for OCDIDs: {jurisdiction_ocdids}")
    await sync_jurisdictions_by_ocdids(jurisdiction_ocdids)
