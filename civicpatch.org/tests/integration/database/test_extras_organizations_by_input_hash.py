"""An organizations run finds another jurisdiction's answer read from the same inputs: the newest
by when its law was collected, from active jurisdictions only. Real Postgres: the lookup is jsonb.

Isolation: sentinel state 'zz', cleaned before and after.
"""

import json

import pytest
import pytest_asyncio
from database.database import get_pool
from database.extras_organizations import get_extras_organizations_by_input_hash

_OLDER = "ocd-jurisdiction/country:us/state:zz/place:zz_hash_older/government"
_NEWER = "ocd-jurisdiction/country:us/state:zz/place:zz_hash_newer/government"
_INACTIVE = "ocd-jurisdiction/country:us/state:zz/place:zz_hash_inactive/government"
_HASH = "zz-input-hash"


def _organizations(collected_at: str, label: str) -> str:
    return json.dumps({
        "posts": [{"role": "member", "label": label, "organization_id": "Selectboard", "maximum_memberships": 3,
                   "sources": [{"url": "https://example.gov/24/033", "note": "three members", "extras": {"source_page_id": "p1", "matched_in": "sentence"}}]}],
        "extras": {"governing_law_collected_at": collected_at, "input_hash": _HASH},
    })


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zz'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _seeded():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid, status, collected_at, label in [
            (_OLDER, "active", "2026-10-21T00:00:00Z", "older"),
            (_NEWER, "active", "2026-10-28T00:00:00Z", "newer"),
            (_INACTIVE, "inactive", "2026-10-29T00:00:00Z", "inactive"),
        ]:
            await cur.execute(
                "INSERT INTO jurisdictions (jurisdiction_ocdid, state, status, data, extras_organizations, updated_at)"
                " VALUES (%s, 'zz', %s, %s, %s::jsonb, now())",
                (ocdid, status, json.dumps({"name": ocdid}), _organizations(collected_at, label)),
            )
        await conn.commit()
    yield
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_newest_active_answer_with_the_hash_is_found():
    found = await get_extras_organizations_by_input_hash(_HASH)

    assert found is not None
    assert [post.label for post in found.posts] == ["newer"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_answer_has_an_unknown_hash():
    assert await get_extras_organizations_by_input_hash("zz-no-such-hash") is None
