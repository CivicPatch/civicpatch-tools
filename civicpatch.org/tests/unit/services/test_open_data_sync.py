"""Unit tests for the tree-diff open-data sync (services/open_data_sync.py).

The pure cores (diff_tree, classify_path, *_rows) are tested in their own modules. Here we
cover the I/O orchestration with the external boundaries mocked (GitHub fetch, DB writes):
the per-kind sync functions (return-synced / None-skip / deactivate-not-in) and sync_all's
wiring (cursor writes, truncation guard, per-run cap).
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from core.open_data.tree_diff import TreeDiff
from lib.github.api import RepoTree
from services.open_data_sync import sync_all, sync_jurisdictions


def _patch(stack, target, **kwargs):
    return stack.enter_context(patch(f"services.open_data_sync.{target}", **kwargs))


# `sync_people` and `bulk_update_people` are gone: open-data is a publish target, and the
# only sync still reading it back is jurisdictions. The two tests here covered the people
# read-back — upserting every file, and excluding a file whose fetch missed — neither of
# which has a subject any more.


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_jurisdictions_upserts_deactivates_and_returns_synced():
    path = "data_source/tx/local/jurisdictions.yml"
    content = yaml.dump({"jurisdictions": [{"id": "ocd-a"}, {"id": "ocd-b"}]})
    with ExitStack() as stack:
        _patch(
            stack,
            "github_service.get_github_file_contents",
            new_callable=AsyncMock,
            side_effect=lambda p: content,
        )
        _patch(
            stack,
            "jurisdictions_db.get_state_names",
            new_callable=AsyncMock,
            return_value={},
        )
        bulk = _patch(
            stack, "jurisdictions_db.bulk_update_jurisdictions", new_callable=AsyncMock
        )
        deact = _patch(
            stack,
            "jurisdictions_db.deactivate_jurisdictions_not_in",
            new_callable=AsyncMock,
        )
        synced = await sync_jurisdictions(TreeDiff(changed=[path], deleted=[]))

    assert synced == [path]
    assert bulk.await_count == 1
    # deactivates anything in the (state, level) NOT in the file's entry ids (within-list removal)
    deact.assert_awaited_once_with("tx", "local", ["ocd-a", "ocd-b"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_jurisdictions_scopes_deactivation_per_level():
    # A state has one jurisdictions.yml per level; each file owns only its own (state, level)
    # slice. A state-file sync must NOT deactivate the state's local rows.
    contents = {
        "data_source/wa/local/jurisdictions.yml": yaml.dump(
            {"jurisdictions": [{"id": "ocd-seattle"}]}
        ),
        "data_source/wa/state/jurisdictions.yml": yaml.dump(
            {"jurisdictions": [{"id": "ocd-wa-gov"}]}
        ),
    }
    with ExitStack() as stack:
        _patch(
            stack,
            "github_service.get_github_file_contents",
            new_callable=AsyncMock,
            side_effect=lambda p: contents[p],
        )
        _patch(
            stack,
            "jurisdictions_db.get_state_names",
            new_callable=AsyncMock,
            return_value={},
        )
        bulk = _patch(
            stack, "jurisdictions_db.bulk_update_jurisdictions", new_callable=AsyncMock
        )
        deact = _patch(
            stack,
            "jurisdictions_db.deactivate_jurisdictions_not_in",
            new_callable=AsyncMock,
        )
        await sync_jurisdictions(TreeDiff(changed=list(contents), deleted=[]))

    # each row carries its file's level (not a hardcoded "local"). Rows arrive across one
    # bulk call per level group, so collect from every call rather than just the last.
    levels = {
        row[0]: row[2] for call in bulk.await_args_list for row in call.args[0]
    }
    assert levels == {"ocd-seattle": "local", "ocd-wa-gov": "state"}
    # one scoped deactivation per file — the state file does not touch the local slice
    calls = {(c.args[0], c.args[1]): c.args[2] for c in deact.await_args_list}
    assert calls == {
        ("wa", "local"): ["ocd-seattle"],
        ("wa", "state"): ["ocd-wa-gov"],
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_jurisdictions_writes_state_level_before_dependent_levels():
    # A dependent row's search_text embeds its state's display name, read back from the
    # stored level='state' row — so the state file must be written first, whatever order
    # the diff tree listed the paths in.
    contents = {
        "data_source/wa/local/jurisdictions.yml": yaml.dump(
            {"jurisdictions": [{"id": "ocd-seattle"}]}
        ),
        "data_source/wa/counties/jurisdictions.yml": yaml.dump(
            {"jurisdictions": [{"id": "ocd-king"}]}
        ),
        "data_source/wa/state/jurisdictions.yml": yaml.dump(
            {"jurisdictions": [{"id": "ocd-wa-gov"}]}
        ),
    }
    with ExitStack() as stack:
        _patch(
            stack,
            "github_service.get_github_file_contents",
            new_callable=AsyncMock,
            side_effect=lambda p: contents[p],
        )
        _patch(
            stack,
            "jurisdictions_db.get_state_names",
            new_callable=AsyncMock,
            return_value={},
        )
        bulk = _patch(
            stack, "jurisdictions_db.bulk_update_jurisdictions", new_callable=AsyncMock
        )
        _patch(
            stack,
            "jurisdictions_db.deactivate_jurisdictions_not_in",
            new_callable=AsyncMock,
        )
        # local listed first — ordering must come from the level, not the input order
        await sync_jurisdictions(TreeDiff(changed=list(contents), deleted=[]))

    written_levels = [call.args[0][0][2] for call in bulk.await_args_list]
    assert written_levels == ["state", "counties", "local"]


# ── sync_all ─────────────────────────────────────────────────────────────────


def _patch_sync_all(stack, tree, stored, contents):
    _patch(
        stack, "environment.get_env_vars", return_value={"OPEN_DATA_REPO_URL": "repo"}
    )
    _patch(stack, "github_service.get_tree", new_callable=AsyncMock, return_value=tree)
    _patch(stack, "get_synced_file_shas", new_callable=AsyncMock, return_value=stored)
    _patch(
        stack,
        "github_service.get_github_file_contents",
        new_callable=AsyncMock,
        side_effect=lambda path: contents.get(path),
    )
    _patch(
        stack,
        "jurisdictions_db.get_state_names",
        new_callable=AsyncMock,
        return_value={},
    )
    _patch(stack, "jurisdictions_db.bulk_update_jurisdictions", new_callable=AsyncMock)
    _patch(
        stack,
        "jurisdictions_db.deactivate_jurisdictions_not_in",
        new_callable=AsyncMock,
    )
    upsert = _patch(stack, "synced_files_db.upsert_synced_file", new_callable=AsyncMock)
    delete = _patch(
        stack, "synced_files_db.delete_synced_files", new_callable=AsyncMock
    )
    return upsert, delete


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_all_writes_cursors_for_changed_jurisdiction_files():
    """Was `..._for_changed_files`, expecting a cursor for the people file too.

    The people file is still in the tree — the assertion is that it is *ignored* now, which is
    the whole change: open-data is a publish target and only jurisdictions are read back.
    """
    tree = RepoTree(
        entries={
            "data_source/tx/local/jurisdictions.yml": "jsha",
            "data/tx/local/a.yml": "psha",
        },
        truncated=False,
    )
    contents = {
        "data_source/tx/local/jurisdictions.yml": yaml.dump(
            {"jurisdictions": [{"id": "ocd-a"}]}
        ),
        "data/tx/local/a.yml": yaml.dump([{"id": "p1"}]),
    }
    with ExitStack() as stack:
        upsert, _delete = _patch_sync_all(
            stack, tree, {}, contents
        )  # empty stored → all new
        await sync_all()

    written = {c.args[0]: c.args[1] for c in upsert.await_args_list}
    assert written == {"data_source/tx/local/jurisdictions.yml": "jsha"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_all_skips_deletion_pass_when_truncated():
    tree = RepoTree(entries={"data/tx/local/a.yml": "psha"}, truncated=True)
    stored = {
        "data/tx/local/gone.yml": "old"
    }  # absent from tree → would normally be deleted
    contents = {"data/tx/local/a.yml": yaml.dump([{"id": "p1"}])}
    with ExitStack() as stack:
        _upsert, delete = _patch_sync_all(stack, tree, stored, contents)
        await sync_all()

    delete.assert_not_awaited()  # truncated tree → deletion pass skipped


# `test_sync_all_caps_people_per_run` went with `_MAX_FILES_PER_RUN`, which existed to bound
# the people backlog — "jurisdictions are few, so cap the people backlog", per its comment.
