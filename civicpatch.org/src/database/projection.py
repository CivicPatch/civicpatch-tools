"""The one writer of the projection.

Every row a publish puts in `people`, `memberships` and `membership_roles` is written from
here and nowhere else, so what "publishing a roster" changes is one place to read. Still
upsert-shaped: the statements are the ones the publish path always ran, moved under one roof
unchanged. The delete-and-rebuild writer replaces them at step 8 of the projector plan.

`tests/unit/database/test_one_writer.py` holds the boundary. The writes still outside it are
each named there with the step that deletes them.
"""

import json
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

import environment
import lib.buckets as buckets

from shared.utils.membership_ids import membership_id
from shared.utils.statuses import ActivityType

from core.projection.membership_details import MembershipSource
from core.projection.people import Membership, Person
from core.projection.live_facts import live_facts
from core.projection.facts import Facts, PostKey
from core.projection.posts import post_keys
from core.projection.roster import Roster, derive_roster, with_published_images
from database import divisions, posts
from database.activity import record_change
from database.facts import load_facts
from database.roles import get_roles
from shared.schemas import RoleConfig
from shared.utils.taxonomy import Taxonomy, build_taxonomy
from schemas.activity import Change
from schemas.assertions import EntityType

_PERSON_COLUMNS = (
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "image",
    "cdn_image",
)
_LIST_COLUMNS = frozenset({"other_names", "phones", "emails", "urls", "source_urls"})

# One statement, so the writers cannot quietly stop agreeing. No `status`: whether somebody is
# on the roster is `IS_ON_THE_ROSTER`, asked of memberships.
# `updated_at` is stamped here, not carried by the caller, so no writer can put a stale value
# back. The WHERE is why it stays meaningful: `DO UPDATE` fires on every conflict whether or not
# anything differs, so without it a republish of an unchanged roster would move every person's
# `updated_at` and diff the published file for nothing.
PERSON_UPSERT = f"""
    INSERT INTO people (id, jurisdiction_ocdid, updated_at, {", ".join(_PERSON_COLUMNS)})
    VALUES (%(id)s, %(jurisdiction_ocdid)s, now(),
            {", ".join(f"%({column})s" for column in _PERSON_COLUMNS)})
    ON CONFLICT (id) DO UPDATE
       SET updated_at = now(),
           {", ".join(f"{column} = EXCLUDED.{column}" for column in _PERSON_COLUMNS)}
     WHERE ({", ".join(f"people.{column}" for column in _PERSON_COLUMNS)})
        IS DISTINCT FROM
           ({", ".join(f"EXCLUDED.{column}" for column in _PERSON_COLUMNS)})
"""


def person_upsert_params(people: list[dict]) -> list[dict]:
    """A roster's dicts as rows for `PERSON_UPSERT`.

    One caller now — `publish_changeset`. It also shaped the people files `od_sync` read back,
    until that read-back was removed.
    """
    return [
        {
            "id": person.get("id"),
            "jurisdiction_ocdid": person.get("jurisdiction_ocdid"),
            **{
                column: (person.get(column) or [])
                if column in _LIST_COLUMNS
                else person.get(column)
                for column in _PERSON_COLUMNS
            },
        }
        for person in people
    ]


def person_rows(people: Iterable[Person], jurisdiction_ocdid: str) -> list[dict]:
    return person_upsert_params(
        [
            {
                "id": person.id,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                **{
                    column: list(value) if column in _LIST_COLUMNS else value
                    for column, value in person.model_dump().items()
                    if column in _PERSON_COLUMNS
                },
            }
            for person in people
        ]
    )


# One publish per jurisdiction at a time: the rebuild deletes and re-inserts, and two at once
# would each insert the other's rows. Transaction-scoped, so a failed publish releases it.
_LOCK_JURISDICTION = "SELECT pg_advisory_xact_lock(hashtext(%s))"

_INSERT_MEMBERSHIP_ROLE = """
    INSERT INTO membership_roles (membership_id, role_id) VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""

_DELETE_OPEN_MEMBERSHIPS = """
    DELETE FROM memberships m USING posts p
    WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s AND m.closed_at IS NULL
"""

# `organization_id` is the post's, joined here rather than carried: a membership cannot
# disagree with its post about which organization it is in.
_INSERT_MEMBERSHIP = """
    INSERT INTO memberships
        (id, post_id, organization_id, person_id, label, start_date, end_date,
         first_seen_at, last_seen_at, designations, meta_unmatched_text, sources)
    SELECT %(id)s, p.id, p.organization_id, %(person_id)s, %(label)s, %(start_date)s,
           %(end_date)s, %(first_seen_at)s, %(last_seen_at)s, %(designations)s,
           %(meta_unmatched_text)s, %(sources)s::jsonb
    FROM posts p WHERE p.id = %(post_id)s
"""


async def _ensure_posts(
    cur, jurisdiction_ocdid: str, keys: Sequence[PostKey], changeset_id: str | None
) -> None:
    """Mint the posts the roster names that do not exist yet, logging each mint."""
    for key in keys:
        await divisions.find_or_create(cur, key.division_ocdid, jurisdiction_ocdid)
        minted = await posts.create_if_absent(
            cur, jurisdiction_ocdid, key.organization_id, key.role_id, key.division_ocdid
        )
        if minted:
            await record_change(
                cur,
                ActivityType.ADD_POST,
                None,
                jurisdiction_ocdid,
                Change(entity_type=EntityType.POST, entity_id=minted, subject=key.role_id),
                changeset_id=changeset_id,
            )


async def _taxonomy(taxonomy: Taxonomy | None) -> Taxonomy:
    if taxonomy is not None:
        return taxonomy
    return build_taxonomy(RoleConfig(roles=await get_roles()))


def _fold(facts: Facts, jurisdiction_ocdid: str, taxonomy: Taxonomy) -> Roster:
    return with_published_images(
        derive_roster(facts, jurisdiction_ocdid, taxonomy),
        buckets.ARTIFACTS,
        environment.get_env_vars()["FRIENDLY_STORAGE_HOST"],
    )


async def derived_roster(
    cur,
    jurisdiction_ocdid: str,
    *,
    including: str | None = None,
    as_of: datetime | None = None,
    taxonomy: Taxonomy | None = None,
) -> Roster:
    """The roster this jurisdiction's facts derive. Nothing is written.

    `including` reads one unpublished changeset as though it had published, which is what a
    proposed roster is (R3): the same fold answers what is live and what a review would make
    live, so a preview cannot disagree with its own outcome. `taxonomy` is for a caller folding
    several changesets of one jurisdiction, which builds it once; the baseline and proposed
    folds of a review also share one `as_of`, so a claim filed between them cannot land on one
    side only.
    """
    facts = await load_facts(
        cur, jurisdiction_ocdid, as_of or datetime.now(timezone.utc), including
    )
    return _fold(facts, jurisdiction_ocdid, await _taxonomy(taxonomy))


async def rebuild_from_facts(
    cur, jurisdiction_ocdid: str, changeset_id: str | None = None
) -> int:
    """The roster every live fact derives, written over the jurisdiction's projection.

    Call it after whatever made a fact true is published, so the fold can see it. Returns the
    number of people written. `post_keys` is read here and nowhere else: its only job is to let
    `rebuild` mint the posts the roster names, which a preview does not do.
    """
    taxonomy = await _taxonomy(None)
    facts = await load_facts(cur, jurisdiction_ocdid, datetime.now(timezone.utc))
    roster = _fold(facts, jurisdiction_ocdid, taxonomy)
    keys = post_keys(live_facts(facts).records, jurisdiction_ocdid, taxonomy)
    await rebuild(cur, jurisdiction_ocdid, roster, keys, changeset_id)
    return len(roster.people)


async def rebuild(
    cur,
    jurisdiction_ocdid: str,
    roster: Roster,
    keys: Sequence[PostKey],
    changeset_id: str | None = None,
) -> None:
    """Replace the jurisdiction's projection with `roster`: every person row upserted, every
    open membership deleted and re-inserted. Closed rows are history and are left alone."""
    await cur.execute(_LOCK_JURISDICTION, (jurisdiction_ocdid,))
    await _ensure_posts(cur, jurisdiction_ocdid, keys, changeset_id)
    people = person_rows(roster.people, jurisdiction_ocdid)
    if people:
        await cur.executemany(PERSON_UPSERT, people)
    await cur.execute(_DELETE_OPEN_MEMBERSHIPS, (jurisdiction_ocdid,))
    memberships = membership_rows(roster.people)
    if memberships:
        await cur.executemany(_INSERT_MEMBERSHIP, memberships)
    roles = membership_role_rows(roster.people)
    if roles:
        await cur.executemany(_INSERT_MEMBERSHIP_ROLE, roles)


def membership_rows(people: Iterable[Person]) -> list[dict]:
    return [
        {
            "id": membership_id(person.id, membership.post.post_id),
            "person_id": person.id,
            "post_id": membership.post.post_id,
            "label": membership.label,
            "start_date": membership.start_date,
            "end_date": membership.end_date,
            "first_seen_at": membership.first_seen_at,
            "last_seen_at": membership.last_seen_at,
            "designations": list(membership.designations),
            "meta_unmatched_text": list(membership.unmatched_text),
            "sources": json.dumps([source.model_dump() for source in membership.sources]),
        }
        for person in people
        for membership in person.memberships
    ]


def membership_role_rows(people: Iterable[Person]) -> list[tuple[str, str]]:
    """`(membership_id, role_id)` for each extra role of each open membership."""
    return [
        (membership_id(person.id, membership.post.post_id), role_id)
        for person in people
        for membership in person.memberships
        for role_id in membership.extra_roles
    ]


# The stored projection as a `Roster`, the stored side of the projection diff. Read-only.
_JURISDICTIONS_WITH_A_ROSTER = """
    SELECT DISTINCT p.jurisdiction_ocdid
    FROM memberships m JOIN posts p ON p.id = m.post_id
    WHERE m.closed_at IS NULL
    ORDER BY p.jurisdiction_ocdid
"""

_STORED_PEOPLE = """
    SELECT id::text, name, other_names, phones, emails, urls, source_urls, image, cdn_image
    FROM people WHERE jurisdiction_ocdid = %s
"""

_STORED_OPEN_MEMBERSHIPS = """
    SELECT m.person_id::text, p.organization_id::text, p.role_id, p.division_ocdid, m.label,
           m.start_date, m.end_date, m.first_seen_at, m.last_seen_at,
           m.designations, m.meta_unmatched_text, m.sources,
           array(
               SELECT r.role_id FROM membership_roles r
               WHERE r.membership_id = m.id ORDER BY r.role_id
           )
    FROM memberships m JOIN posts p ON p.id = m.post_id
    WHERE p.jurisdiction_ocdid = %s AND m.closed_at IS NULL
"""


async def jurisdictions_with_a_roster(cur) -> list[str]:
    await cur.execute(_JURISDICTIONS_WITH_A_ROSTER)
    return [row[0] for row in await cur.fetchall()]


def _stored_membership(row) -> Membership:
    (
        _,
        organization_id,
        role_id,
        division_ocdid,
        label,
        start_date,
        end_date,
        first_seen_at,
        last_seen_at,
        designations,
        unmatched_text,
        sources,
        extra_roles,
    ) = row
    return Membership(
        post=PostKey(
            organization_id=organization_id,
            role_id=role_id,
            division_ocdid=division_ocdid,
        ),
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        label=label,
        start_date=start_date,
        end_date=end_date,
        designations=tuple(designations),
        unmatched_text=tuple(unmatched_text),
        sources=tuple(MembershipSource(**source) for source in sources),
        extra_roles=tuple(extra_roles),
    )


async def stored_roster(cur, jurisdiction_ocdid: str) -> Roster:
    await cur.execute(_STORED_OPEN_MEMBERSHIPS, (jurisdiction_ocdid,))
    memberships: dict[str, list[Membership]] = {}
    for row in await cur.fetchall():
        memberships.setdefault(row[0], []).append(_stored_membership(row))

    await cur.execute(_STORED_PEOPLE, (jurisdiction_ocdid,))
    return Roster(
        people=tuple(
            Person(
                id=row[0],
                name=row[1],
                other_names=tuple(row[2] or ()),
                phones=tuple(row[3] or ()),
                emails=tuple(row[4] or ()),
                urls=tuple(row[5] or ()),
                source_urls=tuple(row[6] or ()),
                image=row[7],
                cdn_image=row[8],
                memberships=tuple(
                    sorted(memberships.get(row[0], ()), key=lambda m: m.post.post_id)
                ),
            )
            for row in sorted(await cur.fetchall())
        )
    )
