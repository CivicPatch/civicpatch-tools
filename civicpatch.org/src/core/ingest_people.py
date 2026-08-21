"""One roster, whichever shape the scrape sent it in.

A submit carries either merged `Official`s — what the pipeline produced while it still did
its own merging — or `PersonRecord`s, one per sighting. Both converge to `Official` here, so
nothing downstream has to know which arrived.

Pure: rows and a taxonomy in, officials out. Both halves are the pipeline's own code, moved
rather than rewritten — `shared.utils.reconcile` is step 05 and `person_to_official` is what
step 07 rendered with — so moving the work does not change what it decides.
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
) -> tuple[list[dict], list[dict]]:
    """The roster a submit implies, as (kept, excluded).

    Excluded means no label resolved to a known role. The pipeline dropped these before the
    wire; they are carried out here so the caller can decide, since a scrape finding somebody
    it cannot classify is a triage question rather than a non-event.

    Dicts rather than `Official`, because an already-merged row is handed back exactly as it
    arrived. `order_official_fields` exists for the fields a roster carries that `Official`
    does not model, and validating a passthrough row would drop every one of them.
    """
    if not rows:
        return [], []

    if _is_official(rows[0]):
        return rows, []

    records = [PersonRecord(**row) for row in rows]
    kept, excluded = reconcile(records, identities, taxonomy, jurisdiction_ocdid, log)
    return _render(kept, taxonomy), _render(excluded, taxonomy)


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


def _render(people: list[Person], taxonomy: Taxonomy) -> list[dict]:
    """Sorted first, because the roster is rendered to a file a human reads and reviews."""
    return [
        order_official_fields(person_to_official(person, taxonomy).model_dump())
        for person in sort_people(people, taxonomy)
    ]
