"""The roster a submit implies: the document a reviewer reads, in the order they read it.

`people_derivation` decides who the people are; this decides how they are presented — sorted,
identified, and rendered. `post_derivation` reads what comes out.

A submit carries `PersonRecord`s, one per sighting, or an already-merged roster from a run that
predates the change. Both converge here, so nothing downstream has to know which arrived.

Pure: rows and a taxonomy in, a roster out.
"""

from core.people_derivation import derived_people
from shared.schemas import Person, PersonRecord
from shared.utils.log_protocol import Log
from shared.utils.official_fields import order_official_fields
from shared.utils.people_utils import person_to_official, sort_people
from shared.utils.person_id_utils import merge_forward_other_names
from shared.utils.taxonomy import Taxonomy


def roster_from_rows(
    rows: list[dict],
    identities: dict[str, list[str]],
    taxonomy: Taxonomy,
    jurisdiction_ocdid: str,
    log: Log,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """The roster a submit implies, and the records behind each of its people.

    Keyed by name, which is the canonical one the derivation grouped on, so the caller can join
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

    derived = derived_people(
        [PersonRecord(**row) for row in rows], identities, taxonomy, jurisdiction_ocdid, log
    )
    records_by_name = {
        person.name: [record.model_dump() for record in records]
        for person, records in derived
    }
    return _render([person for person, _ in derived], taxonomy), records_by_name


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
    """Sorted first, because the roster is rendered to a file a human reads and reviews.

    Carries `labels` as well as `office`, which is the expand half of retiring `Official`.
    `labels` is what a record actually holds; `office.name` is those labels joined with " - "
    here and split apart again by every reader — a round trip through a string that loses
    which label produced what, and reads back as one office named twice.

    `order_official_fields` keeps undeclared keys, so this needs no change to `Official`.
    Readers move to `labels` one at a time; `office` goes when none are left.
    """
    kept = [person for person in people if named_like_a_person(person)]
    return [
        order_official_fields(
            {
                **person_to_official(with_fallback_url(person), taxonomy).model_dump(),
                "labels": with_fallback_url(person).labels,
            }
        )
        for person in sort_people(kept, taxonomy)
    ]


def records_by_person(roster: list[dict], records_by_name: dict) -> dict[str, list[dict]]:
    """Rekey the records from the name they grouped on to the id that name resolved to."""
    return {
        person["id"]: records_by_name[person["name"]]
        for person in roster
        if person["name"] in records_by_name
    }
