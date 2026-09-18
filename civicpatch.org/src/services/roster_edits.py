"""A reviewer's edits to a scrape's roster, and making that roster live.

An edit is an assertion: the scrape's own answer stays in `source_records`, and what a human
said sits beside it. Nothing here overwrites what was scraped.

Adding somebody is a sighting, not an assertion — a human is a source, and a roster is derived
from sightings.

That sighting is filed under the live roster's changeset, not a future scrape's, so it does NOT
make the addition survive the next scrape: `_roster` reads one changeset's sightings, and a
scrape that does not list the person retires them. Accepted — their field values live on as
assertions, their seat does not. An edit to an *existing* person does survive, because
`publish_changeset` re-applies `asserted_values` over whatever the scrape says.
"""

import logging
from typing import List

import services.activity as activity_service
from core.people_edits import (
    PeopleValidationError,
    PersonPatch,
    assertions_from_edit,
    patch_people,
)
from core.changeset_lifecycle import REVIEW_POOL_KINDS
from core.people_roster import reviewer_source_records
from database import assertions, posts
from database.changesets import get_changeset_kind, register_people_edit_changeset
from database.database import get_pool
from database.people import get_roster
from database.source_records import insert_source_records
from schemas.activity import Change
from schemas.common import Identity
from services.publish import promote_images, publish_people, publish_people_edit
from services.roster import proposed_roster, scraped_roster
from shared.schemas import Post
from shared.utils.id_utils import make_id

logger = logging.getLogger(__name__)


class MissingRoster(Exception):
    """The scrape has no recorded roster, so there is nothing to edit or publish."""


class AnonymousEdit(Exception):
    """`assertions.created_by` is NOT NULL: an assertion nobody made is not an assertion."""


class EmptyEdit(Exception):
    """Publishing nobody would retire everyone in the jurisdiction."""


class NotInReviewPool(Exception):
    """A sheet import is decided on its batch page, not from a review card."""


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
    chosen = await _posts_for_additions(_additions(scraped, patched))
    await _record_edits(
        changeset_id, jurisdiction_ocdid, scraped, patched, chosen, user.user_id
    )
    await activity_service.record_manual_edits(
        changeset_id, jurisdiction_ocdid, user.user_id, scraped, patched
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
    chosen = await _posts_for_additions(_additions(base, patched))

    # Its own changeset: the edit is a bundle of changes to one jurisdiction, by one producer,
    # at one time, and it needs to be one — for its own row on the timeline, its own open-data
    # commit url, its own author, and to supersede any older pending scrape. What it must not do
    # is advance `last_seen_at`, and that is `publish_changeset`'s rule, not this one's.
    changeset_id = make_id()
    await register_people_edit_changeset(changeset_id, jurisdiction_ocdid, user.user_id)
    await _record_edits(
        changeset_id, jurisdiction_ocdid, base, patched, chosen, user.user_id
    )

    # A hand edit to an already-live roster publishes in the same beat it happens, unlike a
    # scrape review — so when it touched exactly one person, its own row carries the publish
    # rather than sitting beside a second, generic "Published review" for the same action.
    # More than one person has no single Change to fold onto that row, so those keep today's
    # per-person rows instead.
    try:
        changes = await activity_service.diff_manual_edits(base, patched)
    except Exception:
        logger.exception("Failed to diff manual edits for %s", changeset_id)
        changes = []
    publish_change = changes[0].payload if len(changes) == 1 else None
    if publish_change is None:
        await activity_service.write_person_changes(
            changeset_id, jurisdiction_ocdid, user.user_id, changes
        )

    # The editor sends every person, unchanged ones with no fields; one it left out was removed.
    touched = {edit.id for edit in data if edit.fields}
    patched_ids = {person["id"] for person in patched}
    await publish_people_edit(
        changeset_id,
        jurisdiction_ocdid,
        [person for person in patched if person["id"] in touched],
        _additions(base, patched),
        [person["id"] for person in base if person["id"] not in patched_ids],
        user.user_id,
        changes=publish_change,
    )
    return changeset_id, patched


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
        for claim in assertions_from_edit(
            person["id"], base_by_id.get(person["id"], {}), person, changeset_id
        )
    ]
    await assertions.create_all(claims, user_id)


async def publish_from_review(
    changeset_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str,
) -> None:
    """`publish`, for the review card — which offers only the kinds the review pool does."""
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
    await publish_people(
        changeset_id,
        jurisdiction_ocdid,
        await promote_images(roster),
        resolved_by_user_id,
        changes,
    )
