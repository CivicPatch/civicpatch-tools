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

from core.sync_paths import classify_path


@pytest.mark.unit
def test_people_file_syncs_returns_people():
    assert classify_path("data/tx/local/place_austin.yml") == "people"


@pytest.mark.unit
def test_jurisdictions_file_returns_jurisdictions():
    assert classify_path("data_source/tx/local/jurisdictions.yml") == "jurisdictions"


@pytest.mark.unit
def test_random_py_file_returns_none():
    assert classify_path("scripts/setup_local.py") is None


@pytest.mark.unit
def test_metadata_file_is_not_jurisdictions():
    # The sneaky one: jurisdictions_metadata.yml contains the substring "jurisdictions"
    # but is NOT the list file. A naive `"jurisdictions" in path` would misclassify it.
    assert classify_path("data_source/tx/local/jurisdictions_metadata.yml") is None
