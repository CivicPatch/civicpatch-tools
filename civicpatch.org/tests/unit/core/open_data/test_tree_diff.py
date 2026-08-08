"""Unit tests for the tree-diff core of the open-data sync.

diff_tree(current, stored) compares two {repo_path: blob_sha} maps:
  - current = relevant paths from the CURRENT GitHub tree (already filtered to the files
    we sync — jurisdictions.yml + people files), each mapped to its blob SHA
  - stored  = what synced_files recorded from the LAST sync

and returns a TreeDiff:
  - changed = paths to (re)fetch + upsert — NEW (not in stored) OR MODIFIED (sha differs)
  - deleted = paths gone from the repo    — in stored but ABSENT from current

Unchanged paths (same sha in both) appear in neither list.
"""

import pytest

from core.open_data.tree_diff import diff_tree


@pytest.mark.unit
def test_new_path_is_changed():
    # NEW file: in the tree, never synced before → changed
    result = diff_tree(current={"a.yml": "sha1"}, stored={})
    assert set(result.changed) == {"a.yml"}
    assert result.deleted == []


@pytest.mark.unit
def test_modified_path_is_changed():
    # MODIFIED file: in both, sha differs → changed
    result = diff_tree(current={"a.yml": "new"}, stored={"a.yml": "old"})
    assert set(result.changed) == {"a.yml"}
    assert result.deleted == []


@pytest.mark.unit
def test_missing_from_tree_is_deleted():
    # DELETED file: synced before, gone from the tree → deleted
    result = diff_tree(current={}, stored={"a.yml": "sha1"})
    assert result.changed == []
    assert set(result.deleted) == {"a.yml"}


@pytest.mark.unit
def test_unchanged_path_is_ignored():
    # UNCHANGED file: same sha both sides → neither list
    result = diff_tree(current={"a.yml": "sha1"}, stored={"a.yml": "sha1"})
    assert result.changed == []
    assert result.deleted == []


@pytest.mark.unit
def test_empty_current_deletes_all_stored():
    # whole (filtered) tree empty → everything stored is deleted
    result = diff_tree(current={}, stored={"a.yml": "s1", "b.yml": "s2"})
    assert result.changed == []
    assert set(result.deleted) == {"a.yml", "b.yml"}
