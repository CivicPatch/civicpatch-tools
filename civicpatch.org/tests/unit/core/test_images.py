"""A person's photo through both phases: `local://` references resolved at ingest, and the
re-keying that moves the photo out of the run-scoped artifacts bucket at publish.

A scrape's photo is keyed by the run that produced it; publishing re-keys it by jurisdiction
alone. Dropping `changeset_id` is the whole point: without it a person's photo URL would change
on every re-scrape, so these pin the transformation rather than trusting it.
"""

import pytest

from core.images import (
    artifacts_key,
    cdn_urls,
    local_image_basename,
    promoted_key,
    promoted_url,
    records_with_images,
    resolve_images,
    with_images,
)

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


# --- a whole roster, and the sightings behind it ---

# Downloaded, so the source url is known; whether it was served is the other lookup.
BOTH_SOURCE_URLS = {**SOURCE_URLS, "bo.png": "https://beta.gov/photos/bo.png"}


@pytest.mark.unit
def test_a_photo_that_never_uploaded_is_reported_by_name():
    """`people_collector` logs these. A person is reported only when they carried a `local://`
    reference no upload answered — their source url still resolves, so provenance survives."""
    people = [
        {"name": "Ann Lee", "image": "local://ann.png"},
        {"name": "Bo Ng", "image": "local://bo.png"},
    ]
    resolved, unserved = resolve_images(BOTH_SOURCE_URLS, CDN_URLS, people)
    assert unserved == ["Bo Ng"]
    assert resolved[1]["image"] == "https://beta.gov/photos/bo.png"
    assert "cdn_image" not in resolved[1]


@pytest.mark.unit
def test_a_photo_the_pipeline_never_downloaded_is_reported():
    """Buckley's mayor: seen on one page, `image` a plain url because the download never
    happened, so there was no `local://` ref to notice her by. The old check keyed on that ref
    and skipped her — the question is whether we end up serving the photo, not how we heard
    about it."""
    people = [{"name": "Carolyn Robertson Harding", "image": "https://buckley.gov/1416"}]
    resolved, unserved = resolve_images(SOURCE_URLS, CDN_URLS, people)
    assert unserved == ["Carolyn Robertson Harding"]
    assert "cdn_image" not in resolved[0]


@pytest.mark.unit
def test_a_person_with_no_photo_is_not_reported():
    """Most people have no photo at all; reporting them would bury the real failures."""
    resolved, unserved = resolve_images(SOURCE_URLS, CDN_URLS, [{"name": "Cy Ito"}])
    assert unserved == []
    assert resolved == [{"name": "Cy Ito"}]


@pytest.mark.unit
def test_a_roster_the_pipeline_already_resolved_reports_nothing():
    """The pass runs over already-resolved rosters, and nothing there carries `local://` —
    so an empty cdn map must not be read as every photo having failed."""
    people = [
        {
            "name": "Ann Lee",
            "image": "https://alpha.gov/photos/ann.png",
            "cdn_image": "https://artifacts.civicpatch.org/req/ann.png",
        }
    ]
    resolved, unserved = resolve_images(SOURCE_URLS, {}, people)
    assert unserved == []
    assert resolved == people


@pytest.mark.unit
def test_every_sighting_behind_a_person_resolves_too():
    """A sighting stores both urls itself, so a photo does not have to be looked up through
    the person it was resolved to."""
    records = {"person-1": [{"image": "local://ann.png"}, {"image": "local://ann.png"}]}
    resolved = records_with_images(records, SOURCE_URLS, CDN_URLS)
    assert [r["image"] for r in resolved["person-1"]] == [SOURCE_URLS["ann.png"]] * 2
    assert [r["cdn_image"] for r in resolved["person-1"]] == [CDN_URLS["ann.png"]] * 2


@pytest.mark.unit
def test_a_person_with_no_sightings_keeps_an_empty_list():
    assert records_with_images({"person-1": []}, SOURCE_URLS, CDN_URLS) == {
        "person-1": []
    }


# --- promotion: artifacts bucket → CDN ---

# Whichever bucket the environment writes to; the pure function is told, not told to guess.
ARTIFACTS_BUCKET = "civicpatch-artifacts"

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


# --- the seam between the two phases ---


@pytest.mark.unit
def test_a_url_written_at_ingest_is_readable_at_publish():
    """`cdn_urls` writes the artifacts url and `artifacts_key` parses it back — one string,
    built in one function and regex-matched in another. Change either shape alone and this
    fails here rather than silently skipping every promotion in production."""
    written = cdn_urls(
        {"jane.jpg": f"https://s3.example.com/{ARTIFACTS_BUCKET}/{_ARTIFACTS_KEY}"},
        "https://s3.example.com",
        ARTIFACTS_BUCKET,
        "civicpatch.org",
    )
    assert artifacts_key(written["jane.jpg"], ARTIFACTS_BUCKET) == _ARTIFACTS_KEY


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
