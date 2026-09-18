"""A snapshot of everything publishing derives, as it behaves today.

Step 0 of `.scratch/2026-09-17-plan-projector-refactor.md`: the net under steps 1 and 2, which
extract the fold and make the write replace rather than patch. Neither may change what lands in
the projection, and this is what proves it. It is deliberately broad and deliberately literal:
a characterization test earns its keep by failing when anything moves, so update the expectation
only alongside a change that means to move it.

Covers two bodies in one jurisdiction, a re-scrape of one of them, and a person dropped from the
body that was read: between them they pin the `last_seen_at` ratchet, the org-scoped close, and
the body nothing looked at, which are the three the projector refactor is most likely to move.

`memberships.label` reads NULL throughout, and that is the behaviour: it holds the name a human
asserted (`set_label`), never the source's note, which lives in `sources`.

Isolation: sentinel state 'zc', cleaned before and after.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from core.post_derivation import DerivedMembership, DerivedPost, MembershipSource
from database import divisions, posts
from database.database import get_pool
from database.publications import publish_changeset
from database.source_records import insert_source_records
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zc/place:charville/government"
_BASE = "ocd-division/country:us/state:zc/place:charville"
_WARD_2 = f"{_BASE}/ward:2"
_T0 = datetime.datetime(2026, 3, 11, tzinfo=datetime.timezone.utc)
_T1 = datetime.datetime(2026, 6, 2, tzinfo=datetime.timezone.utc)
_PAGE = "https://zc.gov/council"


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


def _person(person_id: str, name: str) -> dict:
    return {
        "id": person_id,
        "name": name,
        "jurisdiction_ocdid": _OCDID,
        "source_urls": [_PAGE],
    }


def _seat(organization_id: str, role_id: str, division: str, person_id: str, note: str) -> DerivedPost:
    return DerivedPost(
        organization_id=organization_id,
        role_id=role_id,
        role_label=role_id.replace("-", " ").title(),
        division_ocdid=division,
        headcount=1,
        members=[
            DerivedMembership(person_id=person_id, sources=[MembershipSource(note=note, url=_PAGE)])
        ],
    )


async def _record_evidence(
    changeset_id: str, organization_id: str, person_id: str, name: str
) -> None:
    """What the scrape read, in the body it read it for. `close_absent` runs only in the bodies
    a changeset recorded evidence for, so the snapshot depends on this being right."""
    await insert_source_records(
        changeset_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": name,
                    "label": "Member",
                    "source_url": _PAGE,
                    "url": _PAGE,
                    "organization_id": organization_id,
                }
            ]
        },
    )


async def _projection(ids: dict) -> dict:
    """Every derived row, with ids swapped for names so the expectation reads as facts."""
    by_id = {ids["ana"]: "ana", ids["ben"]: "ben"}
    organizations_by_id = {ids["council"]: "council", ids["mayors_office"]: "mayors_office"}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pe.id::text, p.organization_id::text, p.role_id, p.division_ocdid,
                   m.label, m.first_seen_at, m.last_seen_at, m.closed_at,
                   COALESCE((
                       SELECT array_agg(mr.role_id ORDER BY mr.role_id)
                       FROM membership_roles mr WHERE mr.membership_id = m.id
                   ), '{}')
            FROM memberships m
            JOIN posts p ON p.id = m.post_id
            JOIN people pe ON pe.id = m.person_id
            WHERE p.jurisdiction_ocdid = %s
            ORDER BY pe.name, p.role_id, m.first_seen_at
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
                "first_seen_at": row[5],
                "last_seen_at": row[6],
                "closed_at": row[7],
                "extra_roles": list(row[8]),
            }
            for row in rows
        ],
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_two_bodies_derives_this_projection():
    """One scrape, both bodies, one person in each and Ana in both."""
    ids = await _seed()
    changeset_id = await _changeset(_T0)
    await _record_evidence(changeset_id, ids["council"], ids["ana"], "Ana Reyes")
    await _record_evidence(changeset_id, ids["mayors_office"], ids["ben"], "Ben Ortiz")

    await publish_changeset(
        changeset_id,
        _OCDID,
        [_person(ids["ana"], "Ana Reyes"), _person(ids["ben"], "Ben Ortiz")],
        None,
        derived=[
            _seat(ids["council"], "council-member", _WARD_2, ids["ana"], "Council Member Ward 2"),
            _seat(ids["mayors_office"], "mayor", _BASE, ids["ben"], "Mayor"),
        ],
    )

    assert await _projection(ids) == {
        "people": [
            {
                "person": "ana",
                "name": "Ana Reyes",
                "other_names": [],
                "phones": [],
                "emails": [],
                "urls": [],
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
                "urls": [],
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
                "first_seen_at": _T0,
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
                "first_seen_at": _T0,
                "last_seen_at": _T0,
                "closed_at": None,
                "extra_roles": [],
            },
        ]
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_second_scrape_of_one_body_leaves_the_other_alone():
    """The `last_seen_at` ratchet and the org-scoped close, both visible at once: Ana is re-seen
    and her clock advances, Ben is untouched because nothing read his body."""
    ids = await _seed()
    first = await _changeset(_T0)
    await _record_evidence(first, ids["council"], ids["ana"], "Ana Reyes")
    await _record_evidence(first, ids["mayors_office"], ids["ben"], "Ben Ortiz")
    await publish_changeset(
        first,
        _OCDID,
        [_person(ids["ana"], "Ana Reyes"), _person(ids["ben"], "Ben Ortiz")],
        None,
        derived=[
            _seat(ids["council"], "council-member", _WARD_2, ids["ana"], "Council Member Ward 2"),
            _seat(ids["mayors_office"], "mayor", _BASE, ids["ben"], "Mayor"),
        ],
    )

    second = await _changeset(_T1)
    await _record_evidence(second, ids["council"], ids["ana"], "Ana Reyes")
    await publish_changeset(
        second,
        _OCDID,
        [_person(ids["ana"], "Ana Reyes")],
        None,
        derived=[
            _seat(ids["council"], "council-member", _WARD_2, ids["ana"], "Council Member Ward 2")
        ],
    )

    assert await _projection(ids) == {
        "people": [
            {
                "person": "ana",
                "name": "Ana Reyes",
                "other_names": [],
                "phones": [],
                "emails": [],
                "urls": [],
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
                "urls": [],
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
                "first_seen_at": _T0,
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
                "first_seen_at": _T0,
                "last_seen_at": _T0,
                "closed_at": None,
                "extra_roles": [],
            },
        ]
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_body_read_without_someone_closes_them_there():
    """The other half: the council page is read and Ana is not on it, so her council membership
    closes while Ben's, in a body nothing read, does not."""
    ids = await _seed()
    first = await _changeset(_T0)
    await _record_evidence(first, ids["council"], ids["ana"], "Ana Reyes")
    await _record_evidence(first, ids["mayors_office"], ids["ben"], "Ben Ortiz")
    await publish_changeset(
        first,
        _OCDID,
        [_person(ids["ana"], "Ana Reyes"), _person(ids["ben"], "Ben Ortiz")],
        None,
        derived=[
            _seat(ids["council"], "council-member", _WARD_2, ids["ana"], "Council Member Ward 2"),
            _seat(ids["mayors_office"], "mayor", _BASE, ids["ben"], "Mayor"),
        ],
    )

    second = await _changeset(_T1)
    await _record_evidence(second, ids["council"], ids["ben"], "Ben Ortiz")
    await publish_changeset(
        second,
        _OCDID,
        [_person(ids["ben"], "Ben Ortiz")],
        None,
        derived=[_seat(ids["council"], "council-member", _BASE, ids["ben"], "Council Member")],
    )

    closed = {
        (row["person"], row["organization"]): row["closed_at"]
        for row in (await _projection(ids))["memberships"]
    }
    assert closed[("ana", "council")] == _T1
    assert closed[("ben", "mayors_office")] is None
