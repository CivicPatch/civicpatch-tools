"""`local://` photo references resolved into the two urls we store."""

import pytest

from core.image_urls import local_image_basename, with_images

# --- with_images: local:// → where it came from and where we serve it ---

SOURCE_URLS = {"ann.png": "https://alpha.gov/photos/ann.png"}
CDN_URLS = {"ann.png": "https://artifacts.civicpatch.org/req/ann.png"}


@pytest.mark.unit
def test_a_records_local_reference_resolves_to_both_urls():
    """A record carries `local://` on `image` and has no second field to park it in — which
    is why cp.org reads the image map rather than the pipeline."""
    resolved = with_images(
        {"name": "Ann Lee", "image": "local://ann.png"}, SOURCE_URLS, CDN_URLS
    )
    assert resolved["image"] == "https://alpha.gov/photos/ann.png"
    assert resolved["cdn_image"] == "https://artifacts.civicpatch.org/req/ann.png"


@pytest.mark.unit
def test_a_roster_the_pipeline_already_half_resolved_lands_the_same_way():
    """Still the live shape: the pipeline moved the reference to `cdn_image` and put the
    source url on `image`. The pass has to be idempotent over it."""
    resolved = with_images(
        {
            "name": "Ann Lee",
            "image": "https://alpha.gov/photos/ann.png",
            "cdn_image": "local://ann.png",
        },
        SOURCE_URLS,
        CDN_URLS,
    )
    assert resolved["image"] == "https://alpha.gov/photos/ann.png"
    assert resolved["cdn_image"] == "https://artifacts.civicpatch.org/req/ann.png"


@pytest.mark.unit
def test_running_twice_changes_nothing_the_second_time():
    once = with_images(
        {"name": "Ann Lee", "image": "local://ann.png"}, SOURCE_URLS, CDN_URLS
    )
    assert with_images(once, SOURCE_URLS, CDN_URLS) == once


@pytest.mark.unit
def test_a_person_with_no_photo_is_untouched():
    person = {"name": "Ann Lee", "image": None}
    assert with_images(person, SOURCE_URLS, CDN_URLS) is person


@pytest.mark.unit
def test_an_image_that_never_uploaded_keeps_its_source_url():
    """Provenance survives even when we have nothing to serve — the two lookups are
    independent."""
    resolved = with_images(
        {"name": "Ann Lee", "image": "local://ann.png"}, SOURCE_URLS, {}
    )
    assert resolved["image"] == "https://alpha.gov/photos/ann.png"
    assert "cdn_image" not in resolved


@pytest.mark.unit
def test_local_image_basename_reads_either_shape():
    assert local_image_basename({"image": "local://ann.png"}) == "ann.png"
    assert local_image_basename({"cdn_image": "local://ann.png"}) == "ann.png"
    assert local_image_basename({"image": "https://alpha.gov/ann.png"}) is None
