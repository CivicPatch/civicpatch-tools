"""A reviewer's edits to a scrape's roster, and making that roster live.

An edit is an assertion: the scrape's own answer stays in `source_records`, and what a human
said sits beside it. Nothing here overwrites what was scraped.

Adding somebody is a sighting, not an assertion — a human is a source. That is what lets a
manual addition survive: a roster is derived from sightings, so a person without one is gone
by the next read.
"""

import logging
from typing import List

import services.change_logs as change_logs
from core.people_edits import PersonPatch, patch_people, stated_from_edit
from core.people_roster import reviewer_source_records
from database import assertions
from database.source_records import insert_source_records
from schemas.common import Identity
from services.publish import promote_images, promote_to_reviewed, publish_people
from services.roster import proposed_roster, scraped_roster

logger = logging.getLogger(__name__)


class MissingRoster(Exception):
    """The scrape has no recorded roster, so there is nothing to edit or publish."""


class AnonymousEdit(Exception):
    """`assertions.asserted_by` is NOT NULL: an assertion nobody made is not an assertion."""


async def save(
    request_id: str,
    jurisdiction_ocdid: str,
    data: List[PersonPatch],
    user: Identity,
) -> List[dict]:
    """Record the reviewer's edits as assertions against the scrape's own answer."""
    if not user.user_id:
        raise AnonymousEdit(request_id)

    scraped = await scraped_roster(request_id, jurisdiction_ocdid)
    if not scraped:
        raise MissingRoster(request_id)

    patched = patch_people(scraped, data)
    scraped_by_id = {person["id"]: person for person in scraped}

    # Somebody the reviewer added by hand becomes a sighting the same way a scraped person is
    # one — a human is a source. Written before the claims below, so the next read finds them
    # and their fields have somebody to sit on.
    added = {
        person["id"]: [s.model_dump() for s in reviewer_source_records(person)]
        for person in patched
        if person["id"] not in scraped_by_id
    }
    await insert_source_records(
        request_id,
        jurisdiction_ocdid,
        {person_id: rows for person_id, rows in added.items() if rows},
    )

    claims = [
        claim
        for person in patched
        for claim in stated_from_edit(
            person["id"], scraped_by_id.get(person["id"], {}), person
        )
    ]
    await assertions.create_all(claims, user.user_id)
    await change_logs.record_manual_edits(
        request_id, jurisdiction_ocdid, user.user_id, scraped, patched
    )
    return patched


async def publish(
    request_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str | None,
) -> None:
    """Make this scrape's roster live. `edited` is the reviewer's patched result; when they
    published without editing, the submitted roster stands."""
    roster = edited
    if roster is None:
        # `proposed_roster`, not `scraped_roster`: publishing without editing still has to
        # carry what a human stated on an earlier visit.
        roster = await proposed_roster(request_id, jurisdiction_ocdid)
    # Publishing an empty roster retires every person in the jurisdiction. That was unreachable
    # while the review pool required an open PR; the request is the only record now.
    if not roster:
        raise MissingRoster(request_id)
    # Photos promote with the data: publishing is what moves them off the artifacts bucket.
    await publish_people(
        request_id, jurisdiction_ocdid, promote_images(roster), resolved_by_user_id
    )
    # The scrape leaves the unreviewed path for the canonical one. Queued, so a slow or failed
    # GitHub write cannot affect a publish that has already committed.
    await promote_to_reviewed(request_id, jurisdiction_ocdid)
