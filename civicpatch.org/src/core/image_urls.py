"""Turning the pipeline's `local://` photo references into the urls we store.

A scrape downloads photos into its zip and refers to them by hash. Two things matter once the
zip is gone: where the photo came from, and where we serve it. Both are resolved here, from
maps the caller supplies — the file read and the env read are the caller's job.

Nothing here is specific to a person: a sighting and a roster entry are both dicts with an
`image` key, which is what lets one pass serve both.
"""

LOCAL_IMAGE_PREFIX = "local://"


def local_image_basename(person: dict) -> str | None:
    """The downloaded file a photo refers to, if it still refers to one.

    A record carries the reference on `image`; an `Official` the pipeline already formatted
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

    Returns the people and the names of any whose photo was never uploaded — reported rather
    than logged here, so this stays callable without a logger.
    """
    unserved = [
        str(person.get("name"))
        for person in people
        if (basename := local_image_basename(person)) and basename not in cdn_urls
    ]
    return [with_images(person, source_urls, cdn_urls) for person in people], unserved


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
