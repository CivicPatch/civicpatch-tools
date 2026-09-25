"""A reviewer's edits to a scrape's roster, and making that roster live.

An edit is a claim: the scrape's own answer stays in `source_records`, and what a human
said sits beside it. Nothing here overwrites what was scraped.

Adding somebody is a sighting, not a claim — a human is a source, and a roster is derived
from sightings.

That sighting is filed under the live roster's changeset, not a future scrape's, so it does NOT
make the addition survive the next scrape: `_roster` reads one changeset's sightings, and a
scrape that does not list the person retires them. Accepted — their field values live on as
claims, their post does not. An edit to an *existing* person does survive, because
`publish_changeset` re-applies `claimed_values` over whatever the scrape says.
"""

import logging
from typing import List

import services.activity as activity_service
from core.people_edits import (
    PeopleValidationError,
    PersonPatch,
    claims_from_edit,
    patch_people,
)
from core.changeset_lifecycle import REVIEW_POOL_KINDS
from core.people_roster import reviewer_source_records
from database import claims as claims_db, posts
from database.changesets import get_changeset_kind, register_people_edit_changeset
from database.database import get_pool
from database.people import get_roster
from database.source_records import insert_source_records
from schemas.activity import Change
from schemas.common import Identity
from services.publish import publish_roster
from services.roster import proposed_roster, scraped_roster
from shared.schemas import Post

logger = logging.getLogger(__name__)


class MissingRoster(Exception):
    """The scrape has no recorded roster, so there is nothing to edit or publish."""


class AnonymousEdit(Exception):
    """`claims.created_by` is NOT NULL: a claim nobody made is not a claim."""


class EmptyEdit(Exception):
    """Publishing nobody would retire everyone in the jurisdiction."""


class NotInReviewPool(Exception):
    """A sheet import is not bulk-published from the queue."""


async def _chosen_posts(people: list[dict]) -> dict[str, Post]:
    """The post each person was put in, by person id — posts that no longer exist are absent."""
    wanted = {person["id"]: person.get("post_id") for person in people}
    post_ids = list({post_id for post_id in wanted.values() if post_id})
    if not post_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        found = await posts.get_many(cur, post_ids)
    return {
        person_id: found[post_id]
        for person_id, post_id in wanted.items()
        if post_id and post_id in found
    }


def _refuse_postless_additions(new_people: list[dict], chosen: dict[str, Post]) -> None:
    """An addition with no post has nothing for its source record to say, and no organization."""
    failures = [
        {
            "id": person["id"],
            "name": person.get("name"),
            "field": "post_id",
            "message": "Choose a post",
        }
        for person in new_people
        if person["id"] not in chosen
    ]
    if failures:
        raise PeopleValidationError(failures)


def _additions(base: List[dict], patched: List[dict]) -> List[dict]:
    base_ids = {person["id"] for person in base}
    return [person for person in patched if person["id"] not in base_ids]


async def _posts_for_additions(new_people: List[dict]) -> dict[str, Post]:
    """Resolved and refused before any write, so a refused edit leaves no row behind."""
    chosen = await _chosen_posts(new_people)
    _refuse_postless_additions(new_people, chosen)
    return chosen


async def _record_edits(
    changeset_id: str,
    jurisdiction_ocdid: str,
    base: List[dict],
    patched: List[dict],
    chosen: dict[str, Post],
    user_id: str,
) -> None:
    base_by_id = {person["id"]: person for person in base}

    # A human is a source: the record says which post they were given, in its organization.
    added = {
        person["id"]: [
            record.model_dump()
            for record in reviewer_source_records(
                person, chosen[person["id"]].label, chosen[person["id"]].organization_id
            )
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
        for claim in claims_from_edit(
            person["id"], base_by_id.get(person["id"], {}), person, changeset_id
        )
    ]
    await claims_db.create_all(claims, user_id)


async def publish_from_review(
    changeset_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str,
) -> None:
    """`publish`, for bulk review — which offers only the kinds the review pool does."""
    kind = await get_changeset_kind(changeset_id)
    if kind is None:
        raise MissingRoster(changeset_id)
    if kind not in REVIEW_POOL_KINDS:
        raise NotInReviewPool(changeset_id)
    await publish(changeset_id, jurisdiction_ocdid, edited, resolved_by_user_id)


async def publish(
    changeset_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str | None,
    changes: Change | None = None,
) -> None:
    """Make this scrape's roster live.

    Nothing here commits: `WriteRecentChangesWorkflow` mirrors to open-data and the sheets from
    `activity`. The old `publish` / `publish_to_database` split named a choice that
    disappeared when mirroring moved to the sweep, and left the two identical.

    `changes`, when given, rides on the publish's own activity row instead of a separate one —
    see `edit_published`, the only caller that passes it.
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
    await publish_roster(changeset_id, jurisdiction_ocdid, resolved_by_user_id, changes)
