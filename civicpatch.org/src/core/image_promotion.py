"""Where a person's photo lives, before and after review. Pure — no I/O, no storage calls.

A scrape uploads images to the artifacts bucket, keyed by the run that produced them:

    {artifacts}/{request_id}/data_source/{state}/local/{place}/images/{file}

Publishing promotes them to the CDN bucket, keyed by the jurisdiction alone:

    {cdn}/open-data/{state}/local/{place}/images/{file}

Dropping `request_id` is the point of the rename: the permanent key is stable across
re-scrapes, so a person's photo URL does not change every time the pipeline runs.
"""

import re

CDN_KEY_PREFIX = "open-data"


def artifacts_key(cdn_image: str, artifacts_bucket: str) -> str | None:
    """The object key inside the artifacts bucket, or None if this URL is not one of ours —
    an already-promoted image, or a photo hosted on the jurisdiction's own site.

    The bucket is passed in rather than read here: which bucket an environment uses is
    configuration, and this module stays pure.
    """
    # The bucket is a subdomain, so it is always followed by a dot — without anchoring that,
    # `civicpatch-artifacts` also matches `civicpatch-artifacts-nonprod.…`, and a production
    # instance would claim another environment's images as its own.
    pattern = re.compile(rf"https?://{re.escape(artifacts_bucket)}\.[^/]*/(.+)")
    match = pattern.match(cdn_image)
    return match.group(1) if match else None


def promoted_key(key: str) -> str | None:
    """Strip the run-scoped prefix (`{request_id}/data_source/`) and re-root under the CDN
    prefix. None if the key is too short to carry one, which means it was not written by
    `_upload_files` and must not be guessed at."""
    segments = key.split("/")
    if len(segments) <= 2:
        return None
    return "/".join([CDN_KEY_PREFIX, *segments[2:]])


def promoted_url(friendly_storage_host: str, key: str) -> str:
    return f"{friendly_storage_host.rstrip('/')}/{key}"
