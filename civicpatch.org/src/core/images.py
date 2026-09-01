"""A person's photo: where it came from, where we serve it, and where it moves at publish.
Pure — no I/O, no storage calls.

Ingest — a scrape downloads photos into its zip and refers to them by hash. Two things matter
once the zip is gone: where the photo came from, and where we serve it. Both are resolved from
maps the caller supplies — the file read and the env read are the caller's job.

Publish — the photo is promoted out of the run-scoped artifacts bucket:

    {artifacts}/{changeset_id}/data_source/{state}/local/{place}/images/{file}
    {cdn}/open-data/{state}/local/{place}/images/{file}

Dropping `changeset_id` is the point of the rename: the permanent key is stable across
re-scrapes, so a person's photo URL does not change every time the pipeline runs.

The two halves meet on one string: `cdn_urls` builds `https://{artifacts}.{domain}/{key}` at
ingest and `artifacts_key` parses it back at publish. They have to change together, which is
why they live in one file.

Nothing here is specific to a person: a sighting and a roster entry are both dicts with an
`image` key, which is what lets one pass serve both.
"""

import re

LOCAL_IMAGE_PREFIX = "local://"
CDN_KEY_PREFIX = "open-data"


# ── Ingest: local:// references → the urls we store ──────────────────


def local_image_basename(person: dict) -> str | None:
    """The downloaded file a photo refers to, if it still refers to one.

    A record carries the reference on `image`; a roster row already resolved
    has it moved to `cdn_image`, with the source url on `image`. Reading either is what lets
    one pass serve both shapes.
    """
    for value in (person.get("image"), person.get("cdn_image")):
        if value and value.startswith(LOCAL_IMAGE_PREFIX):
            return value.removeprefix(LOCAL_IMAGE_PREFIX)
    return None


def with_images(person: dict, source_urls: dict, cdn_urls: dict) -> dict:
    """Resolve a `local://` photo reference into where it came from and where we serve it.

    Idempotent, so it can run over a roster the pipeline already half-resolved: a person
    whose `image` is a source url and whose `cdn_image` is served is left alone.
    """
    basename = local_image_basename(person)
    if not basename:
        return person
    resolved = {**person}
    if basename in source_urls:
        resolved["image"] = source_urls[basename]
    if basename in cdn_urls:
        resolved["cdn_image"] = cdn_urls[basename]
    return resolved


def cdn_urls(filenames_to_urls: dict, storage_endpoint: str, bucket: str, domain: str) -> dict:
    """Where each uploaded photo is served from, keyed by downloaded filename."""
    return {
        basename: url.replace(f"{storage_endpoint}/{bucket}", f"https://{bucket}.{domain}")
        for basename, url in filenames_to_urls.items()
    }


def resolve_images(
    source_urls: dict, cdn_urls: dict, people: list[dict]
) -> tuple[list[dict], list[str]]:
    """Every `local://` reference turned into where the photo came from and where we serve it.

    Returns the people and the names of any left with a photo we do not serve — reported
    rather than logged here, so this stays callable without a logger.
    """
    resolved = [with_images(person, source_urls, cdn_urls) for person in people]
    # Asked of the *result*: a photo the pipeline never downloaded arrives as a plain url, so
    # `local_image_basename` finds nothing and the old check skipped it silently. Buckley's
    # mayor was the case — one sighting, an `image`, no `cdn_image`, no warning.
    unserved = [
        str(person.get("name"))
        for person in resolved
        if person.get("image") and not person.get("cdn_image")
    ]
    return resolved, unserved


def records_with_images(
    records_by_person: dict[str, list[dict]], source_urls: dict, cdn_urls: dict
) -> dict[str, list[dict]]:
    """The same resolution `resolve_images` does to a roster, applied to the sightings behind it.

    A sighting stores both urls itself, so the photo does not have to be looked up through the
    person it was resolved to.
    """
    return {
        person_id: [with_images(record, source_urls, cdn_urls) for record in records]
        for person_id, records in records_by_person.items()
    }


# ── Publish: artifacts bucket → CDN ──────────────────────────────────


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
    """Strip the run-scoped prefix (`{changeset_id}/data_source/`) and re-root under the CDN
    prefix. None if the key is too short to carry one, which means it was not written by
    `_upload_files` and must not be guessed at."""
    segments = key.split("/")
    if len(segments) <= 2:
        return None
    return "/".join([CDN_KEY_PREFIX, *segments[2:]])


def promoted_url(friendly_storage_host: str, key: str) -> str:
    return f"{friendly_storage_host.rstrip('/')}/{key}"
