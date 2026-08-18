"""commit_unreviewed_scrape — the scrape's first landing place in open-data.

A submitted scrape is committed straight to `main` at its *unreviewed* path, before anyone
has read it. That is only safe because two things keep it out of the live data: the path is
a sibling level (`local-unreviewed`) that `classify_path` refuses to sync, and the reviewed
path is written separately when a human publishes. These pin the path and the branch, since
getting either wrong would silently make unapproved data live.
"""

from unittest.mock import AsyncMock, patch

import pytest

import lib.buckets as buckets

from services.publish import (
    commit_rendered_file,
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
async def test_queues_a_durable_commit_at_the_unreviewed_path():
    """Submit must not block on GitHub, nor lose the write if GitHub is down: the roster is
    already in the database, so the commit is queued and retried rather than attempted once."""
    with patch(
        "lib.temporal.client.enqueue_open_data_commit", new_callable=AsyncMock
    ) as mock_enqueue:
        await commit_unreviewed_scrape(REQUEST_ID, OCDID)

    queued = mock_enqueue.await_args.args[0]
    assert queued.file_path == "data/wa/local-unreviewed/place_seattle.yml"
    assert queued.request_id == REQUEST_ID
    assert queued.jurisdiction_ocdid == OCDID


@pytest.mark.unit
@pytest.mark.asyncio
async def test_queued_commit_carries_no_content():
    """The content is rendered inside the activity, so a retry writes what is true when it
    lands rather than replaying a render captured when the write was queued."""
    with patch(
        "lib.temporal.client.enqueue_open_data_commit", new_callable=AsyncMock
    ) as mock_enqueue:
        await commit_unreviewed_scrape(REQUEST_ID, OCDID)

    queued = mock_enqueue.await_args.args[0]
    assert not hasattr(queued, "content_str")
    assert not hasattr(queued, "people")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commit_rendered_file_renders_from_the_database():
    with (
        patch(
            "services.publish.get_pipeline_run_data_json",
            new_callable=AsyncMock,
            return_value=PEOPLE,
        ),
        patch(
            "lib.github.api.upsert_github_file",
            new_callable=AsyncMock,
            return_value="https://github.com/civicpatch/open-data/commit/abc123",
        ) as mock_upsert,
        patch("services.publish.record_open_data_url", new_callable=AsyncMock) as mock_record,
    ):
        assert await commit_rendered_file(
            "data/wa/local-unreviewed/place_seattle.yml", REQUEST_ID, OCDID, "msg"
        ) == "https://github.com/civicpatch/open-data/commit/abc123"

    kwargs = mock_upsert.await_args.kwargs
    assert kwargs["branch_name"] == "main"
    assert kwargs["file_path"] == "data/wa/local-unreviewed/place_seattle.yml"
    assert "Jane Doe" in kwargs["content_str"]
    # The commit URL is what the UI links to now that there is no pull request.
    mock_record.assert_awaited_once_with(
        REQUEST_ID, "https://github.com/civicpatch/open-data/commit/abc123"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_rejected_write_records_no_url():
    """A retry will land later; recording a URL for a write that did not happen would make the
    request look published to open-data when it is not."""
    with (
        patch(
            "services.publish.get_pipeline_run_data_json",
            new_callable=AsyncMock,
            return_value=PEOPLE,
        ),
        patch("lib.github.api.upsert_github_file", new_callable=AsyncMock, return_value=None),
        patch("services.publish.record_open_data_url", new_callable=AsyncMock) as mock_record,
    ):
        assert await commit_rendered_file("data/x.yml", REQUEST_ID, OCDID, "msg") is None

    mock_record.assert_not_awaited()


# ── image promotion: photos move to the CDN when the data does ──────────────

# Built from the configured bucket, not a literal: the artifacts host follows whichever bucket
# this environment writes to, so a hardcoded one only matches production.
_ARTIFACTS_URL = (
    f"https://{buckets.ARTIFACTS}.civicpatch.org"
    "/2026-02-09-e530/data_source/wa/local/place_seattle/images/jane.jpg"
)


@pytest.mark.unit
def test_promote_images_copies_and_rewrites():
    with patch("lib.storage.copy_object") as mock_copy:
        promoted = promote_images([{"id": "p1", "cdn_image": _ARTIFACTS_URL}])

    mock_copy.assert_called_once()
    args = mock_copy.call_args.args
    # Whichever buckets this environment is configured for — the names are config now, so
    # asserting literals here would pin the test to one deployment.
    assert args[0] == buckets.ARTIFACTS
    assert args[2] == buckets.CDN
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
