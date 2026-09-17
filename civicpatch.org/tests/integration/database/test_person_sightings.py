"""The published roster's `sightings`: each open membership's labels, with the organization they
are held in — the pairing `labels` pools away.

Real Postgres, because the per-membership unnest and the open-only filter are the point.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

from database import divisions, people, posts
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_sightings/government"
_DIVISION = "ocd-division/country:us/state:zz/place:zz_sightings"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _membership(cur, person_id: str, organization_name: str, role_id: str, labels: list[str], closed: bool = False) -> str:
    await cur.execute(
        "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, %s) "
        "ON CONFLICT (jurisdiction_ocdid, name) DO UPDATE SET name = EXCLUDED.name RETURNING id::text",
        (_OCDID, organization_name),
    )
    row = await cur.fetchone()
    assert row is not None
    organization_id = row[0]
    post_id = await posts.find_or_create(cur, _OCDID, organization_id, role_id, _DIVISION)
    await cur.execute(
        """
        INSERT INTO memberships
            (post_id, organization_id, person_id, source_labels, first_seen_at, last_seen_at, closed_at)
        VALUES (%s, %s, %s, %s, now(), now(), CASE WHEN %s THEN now() END)
        """,
        (post_id, organization_id, person_id, labels, closed),
    )
    return organization_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_each_open_membership_keeps_its_labels_with_its_organization():
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await divisions.find_or_create(cur, _DIVISION, _OCDID)
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, 'Ana Reyes')",
            (person_id, _OCDID),
        )
        council = await _membership(cur, person_id, "City Council", "council-member", ["Council Member District 1"])
        mayor = await _membership(cur, person_id, "Office of the Mayor", "mayor", ["Mayor"])
        await _membership(cur, person_id, "School Board", "trustee", ["Trustee"], closed=True)
        await conn.commit()

    [ana] = await people.get_roster(_OCDID)

    assert sorted(ana["sightings"], key=lambda s: s["label"]) == [
        {"label": "Council Member District 1", "source_url": None, "organization_id": council},
        {"label": "Mayor", "source_url": None, "organization_id": mayor},
    ]
