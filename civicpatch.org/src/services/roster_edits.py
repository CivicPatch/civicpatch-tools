"""A human editing one jurisdiction's roster, as claims: the shell around `core/roster_edits.py`.

The client sends each person as it should be. This diffs that against the person the facts
derive and files only the difference, so saving the same screen twice files nothing the second
time. Nothing is overwritten: a claim sits beside the records, and the next rebuild reads both.

Step 9 of the projector plan. It replaces `PATCH /people/data`, `PUT /memberships`,
`DELETE /people/{id}` and the label, close and reject routes, which each wrote a different
shape for the same act.
"""

from core.display_rows import display_rows
from core.people_edits import claim_same_as
from core.projection.diff import on_roster
from core.projection.roster import Roster
from core.roster_edits import claims_for_edit, membership_claim_edits, new_merges
from database import claims as claims_db
from database import memberships as memberships_db
from database import posts as posts_db
from database import projection as projection_db
from database.changesets import (
    find_or_create_review_edit,
    register_people_edit_changeset,
)
from database.database import get_pool
from database.roles import get_roles
from schemas.claims import Claim
from schemas.jurisdictions import PersonEdit
from services.publish import publish_roster
from shared.schemas import RoleConfig
from shared.utils.id_utils import make_id
from shared.utils.taxonomy import Taxonomy, build_taxonomy


class AnonymousEdit(Exception):
    """`claims.created_by` is NOT NULL, and a claim nobody made is not a claim."""


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
    if not user_id:
        raise AnonymousEdit(jurisdiction_ocdid)
    # Under the review's own changeset (9f), so it is attributed and undone on its own.
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        edit_id = await find_or_create_review_edit(
            cur, changeset_id, jurisdiction_ocdid, user_id
        )
        await conn.commit()
    await _file(jurisdiction_ocdid, people, user_id, edit_id, including=changeset_id)
    return edit_id


async def edit_published_roster(
    jurisdiction_ocdid: str, people: list[PersonEdit], user_id: str | None
) -> str:
    """Edit the live roster with no review behind it: mint a changeset, file, publish.

    Returns the changeset id, because undoing the edit is rolling that changeset back.
    """
    if not user_id:
        raise AnonymousEdit(jurisdiction_ocdid)
    await _refuse_unknown_posts(people)

    # Nothing to say, nothing to record. The editor sends every person on the screen, so a save
    # that changed nothing is the normal case, and minting a changeset for it would put an
    # empty edit on the jurisdiction's timeline every time somebody pressed the button.
    changeset_id = make_id()
    claims, membership_edits = await _edit(jurisdiction_ocdid, people, changeset_id)
    if not claims and not membership_edits:
        return ""

    # Read before the claims are filed: this changeset is born published, so once they are
    # written the roster already reflects them and there is no "before" left to read.
    before = on_roster(await _roster(jurisdiction_ocdid))
    await register_people_edit_changeset(changeset_id, jurisdiction_ocdid, user_id)
    await _write(claims, membership_edits, user_id, changeset_id)
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
    claims, membership_edits = await _edit(jurisdiction_ocdid, people, changeset_id, including)
    await _write(claims, membership_edits, user_id, changeset_id)


async def _edit(
    jurisdiction_ocdid: str,
    people: list[PersonEdit],
    changeset_id: str,
    including: str | None = None,
) -> tuple[list[Claim], list[tuple[str, str, str | None]]]:
    """The claims and membership edits (labels, term dates) an edit files.

    A merge moves the absorbed person's claims onto the survivor, so the survivor is diffed
    against the person the merge will make, not the one they were: otherwise an absorbed name
    saved earlier would outrank the survivor's name the reviewer kept.
    """
    derived = await _derived_rows(jurisdiction_ocdid, including)
    merged_into = new_merges(derived, people)
    if merged_into:
        derived = await _derived_rows(jurisdiction_ocdid, including, merged_into)
    claims = [
        *(claim_same_as(absorbed_id, survivor_id, changeset_id)
          for absorbed_id, survivor_id in merged_into.items()),
        *claims_for_edit(derived, people, changeset_id),
    ]
    return claims, membership_claim_edits(derived, people)


async def _write(claims, membership_edits, user_id: str, changeset_id: str) -> None:
    # One transaction, inside `create_all`: half an edit is worse than none, because the half
    # that landed looks like a decision somebody made.
    await claims_db.create_all(claims, user_id)
    if membership_edits:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            for entity_id, field_path, value in membership_edits:
                await memberships_db.set_membership_field(
                    cur, entity_id, field_path, value, user_id, changeset_id
                )
            await conn.commit()


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
    jurisdiction_ocdid: str,
    including: str | None = None,
    merged_into: dict[str, str] | None = None,
) -> tuple[Roster, Taxonomy]:
    """Both, because the caller that turns a roster into rows needs the taxonomy that derived
    it — asking twice is two `get_roles()` round trips for one edit."""
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        roster = await projection_db.derived_roster(
            cur,
            jurisdiction_ocdid,
            including=including,
            taxonomy=taxonomy,
            merged_into=merged_into,
        )
    return roster, taxonomy


async def _derived_rows(
    jurisdiction_ocdid: str,
    including: str | None = None,
    merged_into: dict[str, str] | None = None,
) -> dict[str, dict]:
    """The same roster as the shape `claims_from_edit` diffs against, keyed by person id."""
    roster, taxonomy = await _roster_and_taxonomy(jurisdiction_ocdid, including, merged_into)
    rows = display_rows(on_roster(roster), jurisdiction_ocdid, taxonomy)
    return {row["id"]: row for row in rows}
