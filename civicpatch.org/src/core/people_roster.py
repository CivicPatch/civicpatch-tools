"""The roster a submit implies: the document a reviewer reads, in the order they read it.

`people_derivation` decides who the people are; this decides how they are presented — sorted,
identified, and rendered. `post_derivation` reads what comes out.

A submit carries `PersonRecord`s, one per sighting.

Pure: rows and a taxonomy in, a roster out.
"""

from collections import defaultdict

from shared.schemas import Person, PersonRecord
from shared.utils.log_protocol import Log
from shared.utils.people_utils import sort_people
from shared.utils.person_fields import order_person_fields
from shared.utils.person_id_utils import merge_forward_other_names
from shared.utils.taxonomy import Taxonomy

from core.membership_label import MembershipLabel, derive_post_label, render
from core.people_derivation import (
    term_dates,
    canonical_name,
    derived_people,
    merge_records_to_person,
)
from core.people_roles import derive_roles


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

    Dicts rather than a model, because the roster carries fields no model declares —
    `order_person_fields` places them, and validating on the way through would drop them.
    """
    if not rows:
        return [], {}

    derived = derived_people(
        [PersonRecord(**row) for row in rows],
        identities,
        taxonomy,
        jurisdiction_ocdid,
        log,
    )
    records_by_name = {
        person.name: [record.model_dump() for record in records]
        for person, records in derived
    }
    return _render(derived, taxonomy), records_by_name


def roster_from_sightings(
    sightings: list[dict],
    published: dict[str, Person],
    taxonomy: Taxonomy,
    jurisdiction_ocdid: str,
    log: Log,
) -> list[dict]:
    """The roster a scrape's stored sightings imply — the same document `roster_from_rows`
    produced at ingest, rebuilt from what was kept.

    Grouping is read, not re-derived: `source_record_identities` already answered who is whom,
    and running the name matcher again could answer differently. `published` is who we already
    hold under each resolved id, and is what `identities` was at ingest — it decides the name
    and carries confirmed aliases forward.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for sighting in sightings:
        groups[sighting["person_id"]].append(sighting)

    people = [
        _person_from_sightings(
            person_id, rows, published.get(person_id), jurisdiction_ocdid, taxonomy, log
        )
        for person_id, rows in groups.items()
    ]
    return _render(people, taxonomy)


def _person_from_sightings(
    person_id: str,
    rows: list[dict],
    published: Person | None,
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    log: Log,
) -> tuple[Person, list[PersonRecord]]:
    records = [PersonRecord(**row) for row in rows]
    person = merge_records_to_person(
        log,
        canonical_name(published.name if published else "", records),
        records,
        jurisdiction_ocdid,
        taxonomy,
    )
    # The cdn url of the photo the merge chose, not the most frequent one — the two are a pair
    # and picking them independently can serve a different photo than the one we credited.
    cdn_image = next(
        (
            row["cdn_image"]
            for row in rows
            if row["image"] == person.image and row["cdn_image"]
        ),
        "",
    )
    return (
        person.model_copy(
            update={
                "id": person_id,
                "cdn_image": cdn_image,
                "other_names": _aliases_carried_forward(person, published),
            }
        ),
        records,
    )


def _aliases_carried_forward(person: Person, published: Person | None) -> list[str]:
    """The read's half of `identified`: the scraped spellings plus the aliases a human has
    already confirmed. Without this a name we only know from an earlier scrape is lost."""
    if not published:
        return person.other_names
    return merge_forward_other_names(
        person.name, person.other_names, published.name, published.other_names
    )


def reviewer_source_records(person: dict) -> list[PersonRecord]:
    if not person.get("name"):
        return []
    return [
        PersonRecord(name=person["name"], label="", source_url=source_url)
        for source_url in dict.fromkeys(person.get("source_urls") or [])
        if source_url
    ]


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


def _rendered(
    person: Person, records: list[PersonRecord], taxonomy: Taxonomy
) -> dict:
    """The term comes off the records, not the person: it belongs to the tenure."""
    derived = derive_roles(person.labels, person.jurisdiction_ocdid, taxonomy)
    start_date, end_date = term_dates(records)
    return {
        "name": person.name,
        "other_names": person.other_names,
        "label": render(
            MembershipLabel(
                post_label=derive_post_label(
                    derived.role or "", derived.division_ocdid
                ),
                designations=derived.other_designations,
                unmatched_text=derived.unmatched,
            )
        ),
        "labels": person.labels,
        "division_ocdid": derived.division_ocdid,
        "phones": person.phones,
        "emails": person.emails,
        "urls": person.urls,
        "start_date": start_date or None,
        "end_date": end_date or None,
        "image": person.image,
        "cdn_image": person.cdn_image,
        "jurisdiction_ocdid": person.jurisdiction_ocdid,
        "source_urls": person.source_urls,
        "updated_at": person.updated_at or "",
        "id": person.id,
    }


def _render(
    people: list[tuple[Person, list[PersonRecord]]], taxonomy: Taxonomy
) -> list[dict]:
    """Sorted first, because the roster is rendered to a file a human reads and reviews.

    Carries `labels` and `division_ocdid`, not `office`. They are what `office` held,
    unjoined and unnested: `office.name` was the labels joined with " - ", which read back as
    one office named twice for anyone sighted on pages that spelled it differently.
    """
    records_by_person = {id(person): records for person, records in people}
    kept = [person for person, _ in people if named_like_a_person(person)]
    return [
        order_person_fields(
            _rendered(
                with_fallback_url(person), records_by_person[id(person)], taxonomy
            )
        )
        for person in sort_people(kept, taxonomy)
    ]


def records_by_person(
    roster: list[dict], records_by_name: dict
) -> dict[str, list[dict]]:
    """Rekey the records from the name they grouped on to the id that name resolved to."""
    return {
        person["id"]: records_by_name[person["name"]]
        for person in roster
        if person["name"] in records_by_name
    }
