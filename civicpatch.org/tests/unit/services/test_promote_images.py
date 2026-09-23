"""Promoting a changeset's photos at publish.

The copies are the reason this is worth a test of its own: they are the only network I/O on
the publish request, one blocking round trip per photo, and they used to run in series.

Since the fold writes the roster, promotion is the copy and nothing else: where a promoted
photo lives is `core.images.published_image_url`, a pure function the fold applies.
"""

import time
from unittest.mock import patch

import pytest

import lib.buckets as buckets
from services.publish import promote_changeset_images

pytestmark = pytest.mark.unit

# The bucket is a subdomain, which is what `artifacts_key` anchors on: a URL with it in the
# path parses to nothing, and every copy is silently skipped.
_ARTIFACTS = f"https://{buckets.ARTIFACTS}.storage.example/run-1/data_source/images"
CHANGESET = "c1"


def _images(*names: str):
    """Patch the query that says which photos this changeset brought."""
    return patch(
        "services.publish.source_records_db.changeset_images",
        return_value=[f"{_ARTIFACTS}/{name}.png" for name in names],
    )


@pytest.mark.asyncio
async def test_every_photo_the_changeset_brought_is_copied_once():
    """This test verified that the returned roster kept its order. It now verifies that each
    photo is copied, because promotion no longer returns a roster: the fold derives the rows
    and this only moves the bytes."""
    with _images("ann", "bo", "cy"), patch("lib.storage.copy_object") as copy:
        await promote_changeset_images(CHANGESET)

    assert copy.call_count == 3


@pytest.mark.asyncio
async def test_the_copies_overlap_rather_than_queueing_behind_each_other():
    """The point of the change. Nine councillors were nine serial round trips inside the
    publish request; sleeping in the fake makes serial execution measurable."""

    def slow_copy(*_args, **_kwargs):
        time.sleep(0.05)

    with _images(*(f"p{n}" for n in range(6))), patch(
        "lib.storage.copy_object", side_effect=slow_copy
    ):
        started = time.perf_counter()
        await promote_changeset_images(CHANGESET)
        elapsed = time.perf_counter() - started

    # Six × 50ms is 300ms in series. Generous bound: this asserts "overlapped", not a duration.
    assert elapsed < 0.2


@pytest.mark.asyncio
async def test_a_photo_that_will_not_copy_does_not_fail_the_publish():
    """This test verified that the failing person's record kept the artifacts URL. It now
    verifies that the failure is swallowed, because no record is rewritten here: the fold
    points at the CDN key either way and the sweep is what should retry the copy."""
    with _images("ann", "bo"), patch(
        "lib.storage.copy_object", side_effect=RuntimeError("no such key")
    ) as copy:
        await promote_changeset_images(CHANGESET)

    assert copy.call_count == 2


@pytest.mark.asyncio
async def test_a_changeset_with_no_photos_copies_nothing():
    with _images(), patch("lib.storage.copy_object") as copy:
        await promote_changeset_images(CHANGESET)

    copy.assert_not_called()
