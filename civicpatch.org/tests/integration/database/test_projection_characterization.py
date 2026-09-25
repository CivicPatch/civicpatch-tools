"""A snapshot of everything publishing derives, as it behaves today.

Step 0 of `.scratch/2026-09-17-plan-projector-refactor.md`: the net under steps 1 and 2, which
extract the fold and make the write replace rather than patch. Neither may change what lands in
the projection, and this is what proves it. It is deliberately broad and deliberately literal:
a characterization test earns its keep by failing when anything moves, so update the expectation
only alongside a change that means to move it.

The first three cases cover two bodies in one jurisdiction, a re-scrape of one of them, and a
person dropped from the body that was read: between them they pin the `last_seen_at` ratchet,
the org-scoped close, and the body nothing looked at. Nothing in them changes between scrapes,
so four more exercise the field and post rules: contact details that change, a value a human
rejected that the page keeps printing, a label that maps to no role, and a person who is mayor,
then a member, then mayor again.

`memberships.label` reads NULL throughout, and that is the behaviour: it holds the name a human
claimed (`set_membership_label`), never the source's note, which lives in `sources`.

Each case ends with the projection diff: the fold, run over the same facts, must derive the same
people and open memberships that today's path wrote. Everyone it compares has been scraped at
least once, because `_seed` inserts `people` rows directly and a person with no fact behind them
does not exist to the fold.

Isolation: sentinel state 'zc', cleaned before and after.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from shared.schemas import RoleConfig
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, build_taxonomy

from core.projection.diff import RosterDiff, roster_diff
from core.projection.roster import derive_roster
from database import claims, divisions, posts
from database.database import get_pool
from database.facts import load_facts
from database.projection import stored_roster
from database.publications import publish_changeset
from database.roles import get_roles
from database.source_records import insert_source_records
from schemas.claims import Claim, ClaimKind, EntityType, Source
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zc/place:charville/government"
_BASE = "ocd-division/country:us/state:zc/place:charville"
_WARD_2 = f"{_BASE}/ward:2"
_T0 = datetime.datetime(2026, 3, 11, tzinfo=datetime.timezone.utc)
_T1 = datetime.datetime(2026, 6, 2, tzinfo=datetime.timezone.utc)
_T2 = datetime.datetime(2026, 9, 14, tzinfo=datetime.timezone.utc)
_PAGE = "https://zc.gov/council"
_USER = "zc-reject-user@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,))
        # Changesets before organizations: source records point at both (205, ON DELETE RESTRICT).
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zc'")
        await cur.execute(
            "DELETE FROM claims WHERE created_by IN (SELECT id FROM users WHERE email = %s)",
            (_USER,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_USER,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> dict:
    """A jurisdiction, two bodies, two divisions, two people. Ids are handed back so the
    snapshot can name people rather than print uuids."""
    ids = {"ana": str(uuid.uuid4()), "ben": str(uuid.uuid4())}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zc', 'local')",
            (_OCDID,),
        )
        for name, person_id in (("Ana Reyes", ids["ana"]), ("Ben Ortiz", ids["ben"])):
            await cur.execute(
                "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
                (person_id, _OCDID, name),
            )
        ids["council"] = await factories.default_organization(cur, _OCDID)
        await cur.execute(
            "INSERT INTO organizations (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (mayor_org := str(uuid.uuid4()), _OCDID, "Office of the Mayor"),
        )
        ids["mayors_office"] = mayor_org
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await divisions.find_or_create(cur, _WARD_2, _OCDID)
        await posts.find_or_create(cur, _OCDID, ids["council"], "council-member", _WARD_2)
        await posts.find_or_create(cur, _OCDID, mayor_org, "mayor", _BASE)
        await conn.commit()
    return ids


async def _changeset(at: datetime.datetime) -> str:
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind) VALUES (%s, %s, 'scrape')",
            (changeset_id, _OCDID),
        )
        # Publish reads `updated_at` as the observation's clock.
        await cur.execute(
            "UPDATE changesets SET created_at = %s, updated_at = %s WHERE id = %s",
            (at, at, changeset_id),
        )
        await conn.commit()
    return changeset_id


async def _record_evidence(
    changeset_id: str, organization_id: str, person_id: str, name: str, label: str, **fields
) -> None:
    """What the scrape read, in the organization it read it for. Nobody is retired in an
    organization no record names, so the snapshot depends on this being right.

    `label` must be the one that derives the post the test hands publish: today's path takes
    the post as given, but the fold derives it from this label."""
    await insert_source_records(
        changeset_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": name,
                    "label": label,
                    "source_url": _PAGE,
                    "url": _PAGE,
                    "organization_id": organization_id,
                    **fields,
                }
            ]
        },
    )
    # The insert stamps `now()`; a scrape's records carry its date, and the fold reads those
    # as when the membership was first and last seen.
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE source_records SET created_at = "
            "  (SELECT updated_at FROM changesets WHERE id = %s) WHERE changeset_id = %s",
            (changeset_id, changeset_id),
        )


async def _reject_user() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'admins') RETURNING id::text",
            (_USER, _USER, _USER.replace("@", "-")),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    return row[0]


async def _projection(ids: dict) -> dict:
    """Every derived row, with ids swapped for names so the expectation reads as facts."""
    by_id = {ids["ana"]: "ana", ids["ben"]: "ben"}
    organizations_by_id = {ids["council"]: "council", ids["mayors_office"]: "mayors_office"}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pe.id::text, p.organization_id::text, p.role_id, p.division_ocdid,
                   m.label, m.opened_at, m.last_seen_at, m.closed_at,
                   COALESCE((
                       SELECT array_agg(mr.role_id ORDER BY mr.role_id)
                       FROM membership_roles mr WHERE mr.membership_id = m.id
                   ), '{}')
            FROM memberships m
            JOIN posts p ON p.id = m.post_id
            JOIN people pe ON pe.id = m.person_id
            WHERE p.jurisdiction_ocdid = %s
            ORDER BY pe.name, p.role_id, m.opened_at
            """,
            (_OCDID,),
        )
        rows = await cur.fetchall()
        # Every column `PERSON_UPSERT` writes, so a fold that drops one is caught here.
        await cur.execute(
            """
            SELECT id::text, name, other_names, phones, emails, urls, source_urls,
                   image, cdn_image
            FROM people WHERE jurisdiction_ocdid = %s ORDER BY name
            """,
            (_OCDID,),
        )
        people_rows = await cur.fetchall()
        await cur.execute(
            """
            SELECT organization_id::text, role_id, division_ocdid,
                   meta_is_tracked, meta_headcount
            FROM posts WHERE jurisdiction_ocdid = %s
            ORDER BY role_id, division_ocdid
            """,
            (_OCDID,),
        )
        post_rows = await cur.fetchall()
    return {
        "people": [
            {
                "person": by_id[row[0]],
                "name": row[1],
                "other_names": row[2],
                "phones": row[3],
                "emails": row[4],
                "urls": row[5],
                "source_urls": row[6],
                "image": row[7],
                "cdn_image": row[8],
            }
            for row in people_rows
        ],
        "posts": [
            {
                "organization": organizations_by_id[row[0]],
                "role_id": row[1],
                "division_ocdid": row[2],
                "meta_is_tracked": row[3],
                "meta_headcount": row[4],
            }
            for row in post_rows
        ],
        "memberships": [
            {
                "person": by_id[row[0]],
                "organization": organizations_by_id[row[1]],
                "role_id": row[2],
                "division_ocdid": row[3],
                "label": row[4],
                "opened_at": row[5],
                "last_seen_at": row[6],
                "closed_at": row[7],
                "extra_roles": list(row[8]),
            }
            for row in rows
        ],
    }


async def _projection_diff() -> RosterDiff:
    """The roster diff of stored against derived: the rows today's path wrote, against
    `derive_roster` over the same facts. Empty is R6."""
    roles = await get_roles()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        stored = await stored_roster(cur, _OCDID)
        facts = await load_facts(cur, _OCDID, datetime.datetime.now(datetime.timezone.utc))
    derived = derive_roster(facts, _OCDID, build_taxonomy(RoleConfig(roles=roles)))
    return roster_diff(stored, derived)



@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_two_bodies_derives_this_projection():
    """One scrape, both bodies, one person in each and Ana in both."""
    ids = await _seed()
    changeset_id = await _changeset(_T0)
    await _record_evidence(changeset_id, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2")
    await _record_evidence(changeset_id, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor")

    await publish_changeset(changeset_id, _OCDID)

    assert await _projection(ids) == {
        "people": [
            {
                "person": "ana",
                "name": "Ana Reyes",
                "other_names": [],
                "phones": [],
                "emails": [],
                "urls": [_PAGE],
                "source_urls": [_PAGE],
                "image": None,
                "cdn_image": None,
            },
            {
                "person": "ben",
                "name": "Ben Ortiz",
                "other_names": [],
                "phones": [],
                "emails": [],
                "urls": [_PAGE],
                "source_urls": [_PAGE],
                "image": None,
                "cdn_image": None,
            },
        ],
        "posts": [
            {
                "organization": "council",
                "role_id": "council-member",
                "division_ocdid": _WARD_2,
                "meta_is_tracked": True,
                "meta_headcount": 1,
            },
            {
                "organization": "mayors_office",
                "role_id": "mayor",
                "division_ocdid": _BASE,
                "meta_is_tracked": True,
                "meta_headcount": 1,
            },
        ],
        "memberships": [
            {
                "person": "ana",
                "organization": "council",
                "role_id": "council-member",
                "division_ocdid": _WARD_2,
                "label": None,
                "opened_at": _T0,
                "last_seen_at": _T0,
                "closed_at": None,
                "extra_roles": [],
            },
            {
                "person": "ben",
                "organization": "mayors_office",
                "role_id": "mayor",
                "division_ocdid": _BASE,
                "label": None,
                "opened_at": _T0,
                "last_seen_at": _T0,
                "closed_at": None,
                "extra_roles": [],
            },
        ]
    }

    diff = await _projection_diff()
    assert diff.empty, diff


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_second_scrape_of_one_body_leaves_the_other_alone():
    """The `last_seen_at` ratchet and the org-scoped close, both visible at once: Ana is re-seen
    and her clock advances, Ben is untouched because nothing read his body."""
    ids = await _seed()
    first = await _changeset(_T0)
    await _record_evidence(first, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2")
    await _record_evidence(first, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor")
    await publish_changeset(first, _OCDID)

    second = await _changeset(_T1)
    await _record_evidence(second, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2")
    await publish_changeset(second, _OCDID)

    assert await _projection(ids) == {
        "people": [
            {
                "person": "ana",
                "name": "Ana Reyes",
                "other_names": [],
                "phones": [],
                "emails": [],
                "urls": [_PAGE],
                "source_urls": [_PAGE],
                "image": None,
                "cdn_image": None,
            },
            {
                "person": "ben",
                "name": "Ben Ortiz",
                "other_names": [],
                "phones": [],
                "emails": [],
                "urls": [_PAGE],
                "source_urls": [_PAGE],
                "image": None,
                "cdn_image": None,
            },
        ],
        "posts": [
            {
                "organization": "council",
                "role_id": "council-member",
                "division_ocdid": _WARD_2,
                "meta_is_tracked": True,
                "meta_headcount": 1,
            },
            {
                "organization": "mayors_office",
                "role_id": "mayor",
                "division_ocdid": _BASE,
                "meta_is_tracked": True,
                "meta_headcount": 1,
            },
        ],
        "memberships": [
            {
                "person": "ana",
                "organization": "council",
                "role_id": "council-member",
                "division_ocdid": _WARD_2,
                "label": None,
                "opened_at": _T0,
                "last_seen_at": _T1,
                "closed_at": None,
                "extra_roles": [],
            },
            {
                "person": "ben",
                "organization": "mayors_office",
                "role_id": "mayor",
                "division_ocdid": _BASE,
                "label": None,
                "opened_at": _T0,
                "last_seen_at": _T0,
                "closed_at": None,
                "extra_roles": [],
            },
        ]
    }

    diff = await _projection_diff()
    assert diff.empty, diff


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_body_read_without_someone_drops_them_there():
    """The other half: the council page is read and Ana is not on it, so she no longer holds a
    council membership, while Ben's, in an organization nothing read, stands.

    This test verified that her membership was closed, with `closed_at` set to the scrape's
    date. It now verifies that the membership is gone, because the writer replaces a
    jurisdiction's open memberships with what the facts derive rather than closing what they
    drop. The interval it used to leave behind is `membership_terms`, at step 15."""
    ids = await _seed()
    first = await _changeset(_T0)
    await _record_evidence(first, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2")
    await _record_evidence(first, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor")
    await publish_changeset(first, _OCDID)

    second = await _changeset(_T1)
    await _record_evidence(second, ids["council"], ids["ben"], "Ben Ortiz", "Council Member")
    await publish_changeset(second, _OCDID)

    held = {
        (row["person"], row["organization"])
        for row in (await _projection(ids))["memberships"]
    }
    assert ("ana", "council") not in held
    assert ("ben", "mayors_office") in held

    diff = await _projection_diff()
    assert diff.empty, diff


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_rescrape_that_changes_the_pages_details():
    """Ana's phone and the spelling in her page's aside both change between scrapes. Publish
    overwrites the list columns with what the newest page says; the fold reads her newest
    listing. Ben, whose page was not read again, keeps his."""
    ids = await _seed()
    first = await _changeset(_T0)
    await _record_evidence(
        first, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2",
        phone="(206) 555-0001", other_names=["A. Reyes"],
    )
    await _record_evidence(
        first, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor", phone="(206) 555-0009"
    )
    await publish_changeset(first, _OCDID)

    second = await _changeset(_T1)
    await _record_evidence(
        second, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2",
        phone="(206) 555-0002", other_names=["Ana M. Reyes"],
    )
    await publish_changeset(second, _OCDID)

    people = {row["person"]: row for row in (await _projection(ids))["people"]}
    assert people["ana"]["phones"] == ["(206) 555-0002"]
    assert people["ana"]["other_names"] == ["Ana M. Reyes"]
    assert people["ben"]["phones"] == ["(206) 555-0009"]

    diff = await _projection_diff()
    assert diff.empty, diff


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_rejected_value_stays_gone_when_the_page_keeps_printing_it():
    """A human rejects Ana's phone; the next scrape says it again. Publish drops it through
    `with_claimed_values`, the fold through `stands`, and the projection diff is empty."""
    ids = await _seed()
    user_id = await _reject_user()
    first = await _changeset(_T0)
    await _record_evidence(
        first, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2", phone="(206) 555-0001"
    )
    await _record_evidence(first, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor")
    await publish_changeset(first, _OCDID)
    await claims.create(
        Claim(
            entity_type=EntityType.PERSON,
            entity_id=ids["ana"],
            field_path="phones",
            kind=ClaimKind.REJECT,
            value="(206) 555-0001",
            sources=[Source(note="test")],
        ),
        user_id,
    )

    second = await _changeset(_T1)
    await _record_evidence(
        second, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2", phone="(206) 555-0001"
    )
    await publish_changeset(second, _OCDID)

    people = {row["person"]: row for row in (await _projection(ids))["people"]}
    assert people["ana"]["phones"] == []

    diff = await _projection_diff()
    assert diff.empty, diff


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_label_that_maps_to_no_role_still_holds_a_post():
    """The page calls Ana something the taxonomy has never heard of. She still projects, in a
    post under the unmatched role, with the label there for a human to map later."""
    ids = await _seed()
    changeset_id = await _changeset(_T0)
    await _record_evidence(changeset_id, ids["council"], ids["ana"], "Ana Reyes", "Grand Vizier")
    await _record_evidence(changeset_id, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor")
    await publish_changeset(changeset_id, _OCDID)

    memberships = {
        (row["person"], row["role_id"]) for row in (await _projection(ids))["memberships"]
    }
    assert ("ana", UNMATCHED_ROLE_ID) in memberships

    diff = await _projection_diff()
    assert diff.empty, diff


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mayor_then_member_then_mayor_again():
    """Three scrapes of the council page. Ana is mayor, then a council member, then mayor
    again: two posts, and at the end only the mayor one is open. Each scrape's label is
    parsed on its own, so nothing turns into a Mayor of Ward 2."""
    ids = await _seed()
    steps = (
        (_T0, "Mayor", "mayor", _BASE),
        (_T1, "Council Member Ward 2", "council-member", _WARD_2),
        (_T2, "Mayor", "mayor", _BASE),
    )
    first = await _changeset(_T0)
    await _record_evidence(first, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor")
    await publish_changeset(first, _OCDID)
    for at, label, role_id, division in steps:
        changeset_id = await _changeset(at)
        await _record_evidence(changeset_id, ids["council"], ids["ana"], "Ana Reyes", label)
        await publish_changeset(changeset_id, _OCDID)

    open_now = {
        (row["person"], row["role_id"])
        for row in (await _projection(ids))["memberships"]
        if row["closed_at"] is None
    }
    assert open_now == {("ana", "mayor"), ("ben", "mayor")}

    diff = await _projection_diff()
    assert diff.empty, diff


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_withdrawn_claim_no_longer_counts():
    """A human accepts a name, then it is withdrawn (an admin's rollback, or clearing an
    override today). Today's publish reads `withdrawn_at`; the fold reads the withdraw row that
    214 files alongside it. Both must fall back to what the page says."""
    ids = await _seed()
    user_id = await _reject_user()
    first = await _changeset(_T0)
    await _record_evidence(first, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2")
    await _record_evidence(first, ids["mayors_office"], ids["ben"], "Ben Ortiz", "Mayor")
    await claims.create(
        Claim(
            entity_type=EntityType.PERSON,
            entity_id=ids["ana"],
            field_path="name",
            kind=ClaimKind.ACCEPT,
            value="Ana M. Reyes",
            sources=[Source(note="test")],
        ),
        user_id,
    )
    await publish_changeset(first, _OCDID)
    people = {row["person"]: row for row in (await _projection(ids))["people"]}
    assert people["ana"]["name"] == "Ana M. Reyes"

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        withdrawn = await claims.withdraw(
            cur, EntityType.PERSON, ids["ana"], "name", ClaimKind.ACCEPT, user_id, "typo"
        )
        await conn.commit()
    assert withdrawn == 1

    second = await _changeset(_T1)
    await _record_evidence(second, ids["council"], ids["ana"], "Ana Reyes", "Council Member Ward 2")
    await publish_changeset(second, _OCDID)
    people = {row["person"]: row for row in (await _projection(ids))["people"]}
    assert people["ana"]["name"] == "Ana Reyes"

    diff = await _projection_diff()
    assert diff.empty, diff
