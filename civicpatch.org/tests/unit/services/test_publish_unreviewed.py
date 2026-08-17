"""commit_unreviewed_scrape — the scrape's first landing place in open-data.

A submitted scrape is committed straight to `main` at its *unreviewed* path, before anyone
has read it. That is only safe because two things keep it out of the live data: the path is
a sibling level (`local-unreviewed`) that `classify_path` refuses to sync, and the reviewed
path is written separately when a human publishes. These pin the path and the branch, since
getting either wrong would silently make unapproved data live.
"""

from unittest.mock import AsyncMock, patch

import pytest

from services.publish import (
    commit_unreviewed_scrape,
    promote_images,
    unreviewed_file_path,
)

OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
REQUEST_ID = "2025-09-25-1a2b"
PEOPLE = [{"id": "p1", "name": "Jane Doe"}]


@pytest.mark.unit
def test_path_is_a_sibling_of_the_reviewed_level():
    assert unreviewed_file_path(OCDID) == "data/wa/local-unreviewed/place_seattle.yml"


@pytest.mark.unit
def test_path_is_not_the_reviewed_path():
    """The failure that matters: writing to `local/` would publish unreviewed data."""
    assert unreviewed_file_path(OCDID) != "data/wa/local/place_seattle.yml"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commits_the_roster_to_main_at_the_unreviewed_path():
    with patch(
        "lib.github.api.upsert_github_file", new_callable=AsyncMock, return_value=True
    ) as mock_upsert:
        assert await commit_unreviewed_scrape(REQUEST_ID, OCDID, PEOPLE) is True

    kwargs = mock_upsert.await_args.kwargs
    assert kwargs["branch_name"] == "main"
    assert kwargs["file_path"] == "data/wa/local-unreviewed/place_seattle.yml"
    assert "Jane Doe" in kwargs["content_str"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reports_a_failed_commit_rather_than_raising():
    """The roster is already in the database by this point, so a failed copy must not fail
    the submit that carries it."""
    with patch(
        "lib.github.api.upsert_github_file", new_callable=AsyncMock, return_value=False
    ):
        assert await commit_unreviewed_scrape(REQUEST_ID, OCDID, PEOPLE) is False


# ── image promotion: photos move to the CDN when the data does ──────────────

_ARTIFACTS_URL = (
    "https://civicpatch-artifacts.civicpatch.org"
    "/2026-02-09-e530/data_source/wa/local/place_seattle/images/jane.jpg"
)


@pytest.mark.unit
def test_promote_images_copies_and_rewrites():
    with patch("lib.storage.copy_object") as mock_copy:
        promoted = promote_images([{"id": "p1", "cdn_image": _ARTIFACTS_URL}])

    mock_copy.assert_called_once()
    args = mock_copy.call_args.args
    assert args[0] == "civicpatch-artifacts"
    assert args[2] == "civicpatch"
    assert args[3] == "open-data/wa/local/place_seattle/images/jane.jpg"
    assert promoted[0]["cdn_image"].endswith("/open-data/wa/local/place_seattle/images/jane.jpg")


@pytest.mark.unit
def test_promote_images_leaves_the_record_alone_when_the_copy_fails():
    """A missing photo must not fail the publish — the artifacts URL still resolves."""
    with patch("lib.storage.copy_object", side_effect=Exception("NoSuchKey")):
        promoted = promote_images([{"id": "p1", "cdn_image": _ARTIFACTS_URL}])

    assert promoted[0]["cdn_image"] == _ARTIFACTS_URL


@pytest.mark.unit
def test_promote_images_does_not_mutate_the_input():
    """The caller's roster is also what gets written to open-data; mutating it in place would
    couple the two writes."""
    people = [{"id": "p1", "cdn_image": _ARTIFACTS_URL}]
    with patch("lib.storage.copy_object"):
        promote_images(people)

    assert people[0]["cdn_image"] == _ARTIFACTS_URL
