"""A human editing one jurisdiction's roster, as claims.

The client sends each person as it should be. This diffs that against the person the facts
derive and files only the difference, so saving the same screen twice files nothing the second
time. Nothing is overwritten: a claim sits beside the records, and the next rebuild reads both.

Step 9 of the projector plan. It replaces `PATCH /people/data`, `PUT /memberships`,
`DELETE /people/{id}` and the label, close and reject routes, which each wrote a different
shape for the same act.
"""

from core.card_rows import card_rows
from core.people_edits import (
    PersonPatch,
    assertions_from_edit,
    assertions_from_posts,
    patch_people,
)
from core.projection.diff import on_roster
from core.projection.roster import Roster
from database import assertions as assertions_db
from database import memberships as memberships_db
from database import posts as posts_db
from database import projection as projection_db
from database.changesets import register_people_edit_changeset
from database.database import get_pool
from database.roles import get_roles
from schemas.assertions import Assertion, EntityType
from schemas.jurisdictions import PersonEdit
from services.publish import publish_roster
from shared.schemas import RoleConfig
from shared.utils.id_utils import make_id
from shared.utils.membership_ids import membership_id
from shared.utils.taxonomy import Taxonomy, build_taxonomy


class AnonymousEdit(Exception):
    """`assertions.created_by` is NOT NULL, and a claim nobody made is not a claim."""


class UnknownPost(Exception):
    """An edit naming a post that does not exist.

    Carried over from `memberships.assign`'s 404: the fold ignores a claim whose post it
    cannot find, so without this a typo'd id would file a claim and do nothing, with no word
    to whoever made it.
    """


async def edit_in_review(
    jurisdiction_ocdid: str,
    people: list[PersonEdit],
    user_id: str | None,
    changeset_id: str,
) -> str:
    """Save an edit made while reviewing. Files the claims and stops.

    Nothing publishes: the review is approved as its own act, and a save that went live would
    mean a reviewer could not put work down half-finished.

    The base is what this review proposes, `derive(published + this changeset)`, not what is
    published. A reviewer is correcting the person the card shows them, so a value they
    confirm has to be measured against the scrape's answer — against the published one, a
    correction that happens to match what is already live would file nothing and the publish
    would take the scrape's wrong value.
    """
    await _file(jurisdiction_ocdid, people, user_id, changeset_id, including=changeset_id)
    return changeset_id


async def edit_published_roster(
    jurisdiction_ocdid: str, people: list[PersonEdit], user_id: str | None
) -> str:
    """Edit the live roster with no review behind it: mint a changeset, file, publish.

    Returns the changeset id, because undoing the edit is rolling that changeset back.
    """
    if not user_id:
        raise AnonymousEdit(jurisdiction_ocdid)
    await _refuse_unknown_posts(people)
    derived = await _derived_rows(jurisdiction_ocdid)

    # Nothing to say, nothing to record. The editor sends every person on the screen, so a save
    # that changed nothing is the normal case, and minting a changeset for it would put an
    # empty edit on the jurisdiction's timeline every time somebody pressed the button.
    changeset_id = make_id()
    claims = claims_for_edit(derived, people, changeset_id)
    labels = membership_label_edits(derived, people)
    if not claims and not labels:
        return ""

    # Read before the claims are filed: this changeset is born published, so once they are
    # written the roster already reflects them and there is no "before" left to read.
    before = on_roster(await _roster(jurisdiction_ocdid))
    await register_people_edit_changeset(changeset_id, jurisdiction_ocdid, user_id)
    await _write(claims, labels, user_id, changeset_id)
    # `publish_roster` reads the feed off that against the roster after (9d), so this path
    # records what it changed without diffing its own payload.
    await publish_roster(changeset_id, jurisdiction_ocdid, user_id, before=before)
    return changeset_id


async def _file(
    jurisdiction_ocdid: str,
    people: list[PersonEdit],
    user_id: str | None,
    changeset_id: str,
    including: str | None = None,
) -> None:
    if not user_id:
        raise AnonymousEdit(jurisdiction_ocdid)
    await _refuse_unknown_posts(people)
    derived = await _derived_rows(jurisdiction_ocdid, including)
    await _write(
        claims_for_edit(derived, people, changeset_id),
        membership_label_edits(derived, people),
        user_id,
        changeset_id,
    )


async def _write(claims, labels, user_id: str, changeset_id: str) -> None:
    # One transaction, inside `create_all`: half an edit is worse than none, because the half
    # that landed looks like a decision somebody made.
    await assertions_db.create_all(claims, user_id)
    if labels:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            for entity_id, label in labels:
                await memberships_db.set_membership_label(
                    cur, entity_id, label, user_id, changeset_id
                )
            await conn.commit()


def claims_for_edit(
    derived: dict[str, dict], people: list[PersonEdit], changeset_id: str
) -> list[Assertion]:
    """Pure: the derived roster keyed by person id, and what the client says, in; claims out.

    A person the roster does not derive is an addition, so they have nothing to diff against.
    """
    # Validated and canonicalized before the diff, the way the review save has always done it:
    # a reviewer reformatting a phone the scrape already found must file nothing, and an
    # invalid field must be refused rather than claimed.
    patches = [
        PersonPatch(id=person.id, fields=person.fields)
        for person in people
        if person.fields
    ]
    desired = {
        entry["id"]: entry
        for entry in (patch_people(list(derived.values()), patches) if patches else [])
    }

    claims: list[Assertion] = []
    for person in people:
        published = derived.get(person.id, {"id": person.id})
        if person.id in desired:
            claims.extend(
                assertions_from_edit(
                    person.id, published, desired[person.id], changeset_id
                )
            )
        if person.offices is not None:
            claims.extend(
                assertions_from_posts(
                    person.id,
                    [post["post_id"] for post in published.get("memberships") or []],
                    [office.id for office in person.offices],
                    changeset_id,
                )
            )
    return claims


def membership_label_edits(
    derived: dict[str, dict], people: list[PersonEdit]
) -> list[tuple[str, str | None]]:
    """`(membership_id, membership_label)` for each seat whose name this edit changes.

    Not claims, because clearing a label is a withdrawal, and a withdrawal names a row rather
    than a value. `memberships.set_membership_label` already files both halves, so the shell calls it.
    """
    changes = []
    for person in people:
        held = {
            post["post_id"]: post.get("label")
            for post in (derived.get(person.id) or {}).get("memberships") or []
        }
        for office in person.offices or []:
            if office.membership_label != held.get(office.id):
                changes.append((membership_id(person.id, office.id), office.membership_label))
    return changes


async def _refuse_unknown_posts(people: list[PersonEdit]) -> None:
    wanted = sorted(
        {office.id for person in people for office in person.offices or []}
    )
    if not wanted:
        return
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        known = await posts_db.identities_by_id(cur, wanted)
    missing = [post_id for post_id in wanted if post_id not in known]
    if missing:
        raise UnknownPost(missing)


async def _roster(jurisdiction_ocdid: str, including: str | None = None) -> Roster:
    """The roster the facts derive, as the fold answers it.

    `including` names the review being edited, so the base is what that review proposes rather
    than what is published.
    """
    roster, _taxonomy = await _roster_and_taxonomy(jurisdiction_ocdid, including)
    return roster


async def _roster_and_taxonomy(
    jurisdiction_ocdid: str, including: str | None = None
) -> tuple[Roster, Taxonomy]:
    """Both, because the caller that turns a roster into rows needs the taxonomy that derived
    it — asking twice is two `get_roles()` round trips for one edit."""
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        roster = await projection_db.derived_roster(
            cur, jurisdiction_ocdid, including=including, taxonomy=taxonomy
        )
    return roster, taxonomy


async def _derived_rows(
    jurisdiction_ocdid: str, including: str | None = None
) -> dict[str, dict]:
    """The same roster as the shape `assertions_from_edit` diffs against, keyed by person id."""
    roster, taxonomy = await _roster_and_taxonomy(jurisdiction_ocdid, including)
    rows = card_rows(on_roster(roster), jurisdiction_ocdid, taxonomy)
    return {row["id"]: row for row in rows}
