"""A reviewer's edits to a scrape's roster, and making that roster live.

An edit is an assertion: the scrape's own answer stays in `source_records`, and what a human
said sits beside it. Nothing here overwrites what was scraped.

Adding somebody is a sighting, not an assertion — a human is a source, and a roster is derived
from sightings.

That sighting is filed under the live roster's changeset, not a future scrape's, so it does NOT
make the addition survive the next scrape: `_roster` reads one changeset's sightings, and a
scrape that does not list the person retires them. Accepted — their field values live on as
assertions, their seat does not. An edit to an *existing* person does survive, because
`publish_request` re-applies `stated_values` over whatever the scrape says.
"""

import logging
from typing import List

import services.change_logs as change_logs
from core.people_edits import (
    PeopleValidationError,
    PersonPatch,
    patch_people,
    stated_from_edit,
)
from core.people_roster import reviewer_source_records
from database import assertions, posts
from database.changesets import register_people_edit_request
from database.database import get_pool
from database.people import get_roster
from database.source_records import insert_source_records
from schemas.common import Identity
from services.publish import promote_images, publish_people
from services.roster import proposed_roster, scraped_roster
from shared.utils.id_utils import make_changeset_id

logger = logging.getLogger(__name__)


class MissingRoster(Exception):
    """The scrape has no recorded roster, so there is nothing to edit or publish."""


class AnonymousEdit(Exception):
    """`assertions.asserted_by` is NOT NULL: an assertion nobody made is not an assertion."""


class EmptyEdit(Exception):
    """Publishing nobody would retire everyone in the jurisdiction."""


async def save(
    changeset_id: str,
    jurisdiction_ocdid: str,
    data: List[PersonPatch],
    user: Identity,
) -> List[dict]:
    """Record the reviewer's edits as assertions against the scrape's own answer."""
    if not user.user_id:
        raise AnonymousEdit(changeset_id)

    scraped = await scraped_roster(changeset_id, jurisdiction_ocdid)
    if not scraped:
        raise MissingRoster(changeset_id)

    patched = patch_people(scraped, data)
    labels = await _seat_labels(_additions(scraped, patched))
    await _record_edits(
        changeset_id, jurisdiction_ocdid, scraped, patched, labels, user.user_id
    )
    return patched


async def edit_published(
    jurisdiction_ocdid: str,
    data: List[PersonPatch],
    user: Identity,
) -> tuple[str, List[dict]]:
    if not user.user_id:
        raise AnonymousEdit(jurisdiction_ocdid)

    base = await get_roster(jurisdiction_ocdid=jurisdiction_ocdid)
    patched = patch_people(base, data)
    if not patched:
        raise EmptyEdit(jurisdiction_ocdid)
    # Before the first write: a request row with nothing behind it still counts as a
    # supersedor and would sweep every pending card for the jurisdiction.
    labels = await _seat_labels(_additions(base, patched))

    # Its own changeset: the edit is a bundle of changes to one jurisdiction, by one producer,
    # at one time, and it needs to be one — for its own row on the timeline, its own open-data
    # commit url, its own author, and to supersede any older pending scrape. What it must not do
    # is advance `last_seen_at`, and that is `publish_request`'s rule, not this one's.
    changeset_id = make_changeset_id()
    await register_people_edit_request(changeset_id, jurisdiction_ocdid, user.user_id)
    await _record_edits(
        changeset_id, jurisdiction_ocdid, base, patched, labels, user.user_id
    )
    await publish(changeset_id, jurisdiction_ocdid, patched, user.user_id)
    return changeset_id, patched


async def _chosen_post_labels(people: list[dict]) -> dict[str, str]:
    """The seat each person was put in, by person id — the post's own label, which reads as a
    source would have written it."""
    wanted = {person["id"]: person.get("post_id") for person in people}
    post_ids = list({post_id for post_id in wanted.values() if post_id})
    if not post_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await posts.get_many(cur, post_ids)
    return {
        person_id: found[post_id].label if post_id in found else ""
        for person_id, post_id in wanted.items()
        if post_id
    }


def _refuse_postless_additions(new_people: list[dict], labels: dict[str, str]) -> None:
    """An addition with no seat has nothing for its sighting to say and would land on
    `unmatched`. A `post_id` naming no post fails the same way: it resolves to no label."""
    failures = [
        {
            "id": person["id"],
            "name": person.get("name"),
            "field": "post_id",
            "message": "Choose a post",
        }
        for person in new_people
        if not labels.get(person["id"])
    ]
    if failures:
        raise PeopleValidationError(failures)


def _additions(base: List[dict], patched: List[dict]) -> List[dict]:
    base_ids = {person["id"] for person in base}
    return [person for person in patched if person["id"] not in base_ids]


async def _seat_labels(new_people: List[dict]) -> dict[str, str]:
    """Resolved and refused before any write, so a refused edit leaves no row behind."""
    labels = await _chosen_post_labels(new_people)
    _refuse_postless_additions(new_people, labels)
    return labels


async def _record_edits(
    changeset_id: str,
    jurisdiction_ocdid: str,
    base: List[dict],
    patched: List[dict],
    labels: dict[str, str],
    user_id: str,
) -> None:
    base_by_id = {person["id"]: person for person in base}

    # A human is a source: the sighting says which seat they were given.
    added = {
        person["id"]: [
            record.model_dump()
            for record in reviewer_source_records(person, labels[person["id"]])
        ]
        for person in _additions(base, patched)
    }
    await insert_source_records(
        changeset_id,
        jurisdiction_ocdid,
        {person_id: rows for person_id, rows in added.items() if rows},
    )

    claims = [
        claim
        for person in patched
        for claim in stated_from_edit(
            person["id"], base_by_id.get(person["id"], {}), person
        )
    ]
    await assertions.create_all(claims, user_id)
    await change_logs.record_manual_edits(
        changeset_id, jurisdiction_ocdid, user_id, base, patched
    )


async def publish_to_database(
    changeset_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str | None,
) -> None:
    """Make this scrape's roster live, without mirroring it into open-data.

    Separate from `publish` for the sake of bulk publishing, which mirrors every jurisdiction it
    made live in one commit rather than one each. Anything publishing a single jurisdiction
    wants `publish` — this on its own leaves open-data behind the database.
    """
    roster = edited
    if roster is None:
        # `proposed_roster`, not `scraped_roster`: publishing without editing still has to
        # carry what a human stated on an earlier visit.
        roster = await proposed_roster(changeset_id, jurisdiction_ocdid)
    # Publishing an empty roster retires every person in the jurisdiction. That was unreachable
    # while the review pool required an open PR; the request is the only record now.
    if not roster:
        raise MissingRoster(changeset_id)
    # Photos promote with the data: publishing is what moves them off the artifacts bucket.
    await publish_people(
        changeset_id, jurisdiction_ocdid, promote_images(roster), resolved_by_user_id
    )


async def publish(
    changeset_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str | None,
) -> None:
    await publish_to_database(
        changeset_id, jurisdiction_ocdid, edited, resolved_by_user_id
    )
