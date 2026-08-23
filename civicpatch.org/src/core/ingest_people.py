"""One roster, whichever shape the scrape sent it in.

A submit carries `PersonRecord`s, one per sighting, or merged `Official`s from a run that
predates the change. Both converge to `Official` here, so nothing downstream has to know
which arrived.

Pure: rows and a taxonomy in, officials out.
"""

from shared.schemas import Person, PersonRecord
from shared.utils.log_protocol import Log
from shared.utils.official_fields import order_official_fields
from shared.utils.people_utils import person_to_official, sort_people
from shared.utils.person_id_utils import merge_forward_other_names
from shared.utils.reconcile import reconcile
from shared.utils.taxonomy import Taxonomy


def officials_from_rows(
    rows: list[dict],
    identities: dict[str, list[str]],
    taxonomy: Taxonomy,
    jurisdiction_ocdid: str,
    log: Log,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """The roster a submit implies, and the records behind each of its people.

    Keyed by name, which is the canonical one `reconcile` grouped on, so the caller can join
    on the roster entry it just gave an id to.

    Everyone the scrape saw is in it.

    Whether a post is one we diff against is `posts.is_tracked`, decided when the post is
    minted — not here, and not by dropping the person.

    Dicts rather than `Official`, because an already-merged row is handed back exactly as it
    arrived. `order_official_fields` exists for the fields a roster carries that `Official`
    does not model, and validating a passthrough row would drop every one of them.
    """
    if not rows:
        return [], {}

    if _is_official(rows[0]):
        return rows, {}

    reconciled = reconcile(
        [PersonRecord(**row) for row in rows], identities, taxonomy, jurisdiction_ocdid, log
    )
    records_by_name = {
        person.name: [record.model_dump() for record in records]
        for person, records in reconciled
    }
    return _render([person for person, _ in reconciled], taxonomy), records_by_name


def identified(person: dict, resolution: dict) -> dict:
    """One roster entry carrying the identity cp.org resolved for it.

    An unmatched or ambiguous resolution leaves `other_names` alone: there is no confirmed
    entity to carry aliases forward from, and guessing would put them on the wrong person.
    """
    with_id = {**person, "id": resolution["id"] or ""}
    matched = resolution["person"]
    if not matched or resolution["ambiguous"]:
        return with_id
    return {
        **with_id,
        "other_names": merge_forward_other_names(
            person["name"],
            person.get("other_names") or [],
            matched.name,
            matched.other_names,
        ),
    }


LOCAL_IMAGE_PREFIX = "local://"


def local_image_basename(person: dict) -> str | None:
    """The downloaded file a person's photo refers to, if it still refers to one.

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


def _is_official(row: dict) -> bool:
    """`office` is required on `Official` and absent from every record, so its presence is
    the whole discriminator."""
    return "office" in row


# Below this, a "name" is a label the extractor read as a person — "Vacant", "Mayor",
# a heading. Two words is a thin test and it has never been measured, but a scrape that
# reports the word "Vacant" as a councillor is worse than one that reports nobody.
MINIMUM_NAME_WORDS = 2


def named_like_a_person(person: Person) -> bool:
    return len(person.name.split()) >= MINIMUM_NAME_WORDS


def with_fallback_url(person: Person) -> Person:
    """Somewhere to send a reader. Someone with no url of their own gets the page they were
    found on, which is the next best answer to "where does this come from"."""
    if person.urls or not person.source_urls:
        return person
    return person.model_copy(update={"urls": [person.source_urls[0]]})


def _render(people: list[Person], taxonomy: Taxonomy) -> list[dict]:
    """Sorted first, because the roster is rendered to a file a human reads and reviews."""
    kept = [person for person in people if named_like_a_person(person)]
    return [
        order_official_fields(
            person_to_official(with_fallback_url(person), taxonomy).model_dump()
        )
        for person in sort_people(kept, taxonomy)
    ]


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


def images_by_person(roster: list[dict]) -> dict[str, dict]:
    """Each person's resolved photo urls, keyed by id."""
    return {
        person["id"]: {key: person[key] for key in ("image", "cdn_image") if person.get(key)}
        for person in roster
        if person.get("id")
    }


def records_by_person(roster: list[dict], records_by_name: dict) -> dict[str, list[dict]]:
    """Rekey the records from the name they grouped on to the id that name resolved to."""
    return {
        person["id"]: records_by_name[person["name"]]
        for person in roster
        if person["name"] in records_by_name
    }
