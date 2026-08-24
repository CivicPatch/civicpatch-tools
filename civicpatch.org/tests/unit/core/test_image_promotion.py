"""Unit tests for image_upload — where a person's photo lives before and after review.

A scrape's photo is keyed by the run that produced it; publishing re-keys it by jurisdiction
alone. Dropping `request_id` is the whole point: without it a person's photo URL would change
on every re-scrape, so these pin the transformation rather than trusting it.
"""

import pytest

# Whichever bucket the environment writes to; the pure function is told, not told to guess.
ARTIFACTS_BUCKET = "civicpatch-artifacts"

from core.image_upload import artifacts_key, promoted_key, promoted_url

_ARTIFACTS_URL = (
    "https://civicpatch-artifacts.civicpatch.org"
    "/2026-02-09-e530/data_source/wa/local/place_seattle/images/jane.jpg"
)
_ARTIFACTS_KEY = "2026-02-09-e530/data_source/wa/local/place_seattle/images/jane.jpg"


@pytest.mark.unit
def test_extracts_the_key_from_an_artifacts_url():
    assert artifacts_key(_ARTIFACTS_URL, ARTIFACTS_BUCKET) == _ARTIFACTS_KEY


@pytest.mark.unit
def test_ignores_a_photo_hosted_elsewhere():
    """Plenty of people carry a photo URL from the jurisdiction's own site — not ours to move."""
    assert artifacts_key("https://seattle.gov/img/jane.jpg", ARTIFACTS_BUCKET) is None


@pytest.mark.unit
def test_ignores_an_already_promoted_url():
    """Publishing twice must not try to re-promote, or the second copy would 404."""
    assert (
        artifacts_key(
            "https://cdn.civicpatch.org/open-data/wa/local/x/images/j.jpg",
            ARTIFACTS_BUCKET,
        )
        is None
    )


@pytest.mark.unit
def test_promotion_drops_the_run_scoped_prefix():
    assert (
        promoted_key(_ARTIFACTS_KEY)
        == "open-data/wa/local/place_seattle/images/jane.jpg"
    )


@pytest.mark.unit
def test_promoted_key_is_stable_across_re_scrapes():
    """The property that matters: two runs of the same jurisdiction land on one permanent key."""
    first = promoted_key("run-one/data_source/wa/local/place_seattle/images/jane.jpg")
    second = promoted_key("run-two/data_source/wa/local/place_seattle/images/jane.jpg")
    assert first == second


@pytest.mark.unit
def test_refuses_a_key_with_no_prefix_to_strip():
    """Not written by _upload_files, so its shape is unknown and must not be guessed at."""
    assert promoted_key("jane.jpg") is None
    assert promoted_key("images/jane.jpg") is None


@pytest.mark.unit
def test_promoted_url_does_not_double_the_separator():
    key = "open-data/wa/local/place_seattle/images/jane.jpg"
    assert promoted_url("https://cdn.civicpatch.org/", key) == (
        f"https://cdn.civicpatch.org/{key}"
    )


@pytest.mark.unit
def test_a_different_environments_bucket_is_recognised():
    """The bucket is configuration: a nonprod deployment writing to its own bucket must still
    have its own URLs recognised as promotable, or nothing would ever be promoted there."""
    url = "https://civicpatch-artifacts-nonprod.civicpatch.org/req-1/data_source/wa/local/x/images/j.png"
    assert (
        artifacts_key(url, "civicpatch-artifacts-nonprod")
        == "req-1/data_source/wa/local/x/images/j.png"
    )
    # ...and the production bucket's URLs are not its business.
    assert artifacts_key(url, "civicpatch-artifacts") is None
