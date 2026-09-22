from core.images import published_image_url

_BUCKET = "civicpatch-artifacts-nonprod"
_HOST = "https://civicpatch-nonprod.civicpatch.org"


def test_an_artifact_maps_to_its_promoted_url():
    artifact = (
        f"https://{_BUCKET}.civicpatch.org/"
        "d38b8527/data_source/wa/local/place_seattle/images/ef06d9a9e07d.png"
    )

    assert published_image_url(artifact, _BUCKET, _HOST) == (
        f"{_HOST}/open-data/wa/local/place_seattle/images/ef06d9a9e07d.png"
    )


def test_an_image_that_is_not_our_artifact_is_unchanged():
    """An already-promoted image, or one hosted on the jurisdiction's own site."""
    elsewhere = "https://seattle.gov/images/Council/Members/saka.jpg"

    assert published_image_url(elsewhere, _BUCKET, _HOST) == elsewhere


def test_no_image_stays_no_image():
    assert published_image_url(None, _BUCKET, _HOST) is None
