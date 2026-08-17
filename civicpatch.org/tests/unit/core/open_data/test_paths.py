"""Unit tests for classify_path — decides what kind of file a repo path is, so the sync
knows (a) which tree paths it cares about and (b) how to route each change.

classify_path(path) -> "jurisdictions" | "people" | None
  - "jurisdictions" : a data_source/.../jurisdictions.yml (the per-state list file)
  - "people"        : a data/....yml (a per-jurisdiction people file)
  - None            : anything else (README, jurisdictions_metadata.yml, validation
                      outputs, scripts, ...) — not synced

Example real paths:
  data/tx/local/place_austin.yml                  -> "people"
  data_source/tx/local/jurisdictions.yml          -> "jurisdictions"
  data_source/tx/local/jurisdictions_metadata.yml -> None
  README.md                                        -> None
"""

import pytest

from core.open_data.paths import (
    SyncFileKind,
    classify_path,
    jurisdiction_path_parts,
    jurisdictions_file_path,
    level_ordered_batches,
)


@pytest.mark.unit
def test_people_file_syncs_returns_people():
    assert classify_path("data/tx/local/place_austin.yml") is SyncFileKind.PEOPLE


@pytest.mark.unit
def test_jurisdictions_file_returns_jurisdictions():
    assert (
        classify_path("data_source/tx/local/jurisdictions.yml")
        is SyncFileKind.JURISDICTIONS
    )


@pytest.mark.unit
def test_random_py_file_returns_none():
    assert classify_path("scripts/setup_local.py") is None


@pytest.mark.unit
def test_metadata_file_is_not_jurisdictions():
    # The sneaky one: jurisdictions_metadata.yml contains the substring "jurisdictions"
    # but is NOT the list file. A naive `"jurisdictions" in path` would misclassify it.
    assert classify_path("data_source/tx/local/jurisdictions_metadata.yml") is None


# ── level_ordered_batches ────────────────────────────────────────────────────


@pytest.mark.unit
def test_batches_are_ordered_state_then_counties_then_local():
    # Dependent levels are built from their state's stored row, so state goes first.
    # Input order is deliberately wrong to prove the order comes from the level.
    batches = level_ordered_batches(
        [
            "data_source/wa/local/jurisdictions.yml",
            "data_source/wa/state/jurisdictions.yml",
            "data_source/wa/counties/jurisdictions.yml",
        ]
    )
    assert batches == [
        ["data_source/wa/state/jurisdictions.yml"],
        ["data_source/wa/counties/jurisdictions.yml"],
        ["data_source/wa/local/jurisdictions.yml"],
    ]


@pytest.mark.unit
def test_absent_levels_are_skipped_not_emitted_empty():
    batches = level_ordered_batches(["data_source/tx/local/jurisdictions.yml"])
    assert batches == [["data_source/tx/local/jurisdictions.yml"]]


@pytest.mark.unit
def test_paths_of_the_same_level_share_one_batch_across_states():
    batches = level_ordered_batches(
        [
            "data_source/tx/local/jurisdictions.yml",
            "data_source/wa/local/jurisdictions.yml",
        ]
    )
    assert len(batches) == 1
    assert len(batches[0]) == 2


@pytest.mark.unit
def test_unknown_level_sorts_last():
    # An unrecognised level still syncs; it just cannot be a dependency of the known ones.
    batches = level_ordered_batches(
        [
            "data_source/wa/territories/jurisdictions.yml",
            "data_source/wa/state/jurisdictions.yml",
        ]
    )
    assert batches == [
        ["data_source/wa/state/jurisdictions.yml"],
        ["data_source/wa/territories/jurisdictions.yml"],
    ]


@pytest.mark.unit
def test_empty_input_returns_no_batches():
    assert level_ordered_batches([]) == []


@pytest.mark.unit
def test_path_parts_returns_state_and_level():
    assert jurisdiction_path_parts("data_source/tx/local/jurisdictions.yml") == (
        "tx",
        "local",
    )


# ── jurisdictions_file_path ──────────────────────────────────────────────────


@pytest.mark.unit
def test_place_under_state_is_local():
    path = jurisdictions_file_path(
        "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
    )
    assert path == "data_source/wa/local/jurisdictions.yml"


@pytest.mark.unit
def test_place_under_county_is_still_local():
    # The county segment locates the place; it does not make it a county. Albion
    # township lives in MI's local list, not its counties list.
    path = jurisdictions_file_path(
        "ocd-jurisdiction/country:us/state:mi/county:calhoun/place:albion/government"
    )
    assert path == "data_source/mi/local/jurisdictions.yml"


@pytest.mark.unit
def test_county_without_a_place_is_counties():
    # Regression: this used to resolve to the state's local list, which does not
    # contain King County at all, so a targeted refresh silently synced the wrong file.
    path = jurisdictions_file_path(
        "ocd-jurisdiction/country:us/state:wa/county:king/government"
    )
    assert path == "data_source/wa/counties/jurisdictions.yml"


@pytest.mark.unit
def test_state_only_is_state():
    path = jurisdictions_file_path("ocd-jurisdiction/country:us/state:wa/government")
    assert path == "data_source/wa/state/jurisdictions.yml"


# ── unreviewed scrapes are visible in the repo but must never sync ──────────


@pytest.mark.unit
def test_unreviewed_people_file_does_not_sync():
    """It matches every clause a reviewed people file matches, so the exclusion is the only
    thing keeping unapproved data out of `people`."""
    assert classify_path("data/tx/local-unreviewed/place_austin.yml") is None


@pytest.mark.unit
def test_reviewed_sibling_still_syncs():
    assert classify_path("data/tx/local/place_austin.yml") is SyncFileKind.PEOPLE


@pytest.mark.unit
def test_unreviewed_suffix_only_matches_the_level_segment():
    """The suffix is meaningful on the level, not anywhere in the path — a place that happens
    to end in it is still reviewed data."""
    assert (
        classify_path("data/tx/local/place_austin-unreviewed.yml")
        is SyncFileKind.PEOPLE
    )
