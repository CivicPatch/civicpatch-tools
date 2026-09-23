"""The ids migrations mint in SQL agree with the ones the fold computes in Python.

Migrations 216 onward compute `post_key_id` and `membership_id` in temporary SQL functions,
`uuid_generate_v5` over a namespace and a `|`-joined encoding. If either ever drifts from the
Python, every copied claim is addressed to a membership the fold never computes, and nothing
says so. These pin the namespaces and encodings.
"""

import uuid
from pathlib import Path
from typing import LiteralString

import pytest
from shared.utils.membership_ids import MEMBERSHIP_NAMESPACE, membership_id

from core.projection.facts import POST_NAMESPACE, PostKey
from database.database import get_pool

_ORGANIZATION = "11111111-1111-1111-1111-111111111111"
_PERSON = "22222222-2222-2222-2222-222222222222"
_DIVISION = "ocd-division/country:us/state:wa/place:seattle"


async def _uuid5(namespace: uuid.UUID, name: str) -> str:
    sql: LiteralString = "SELECT uuid_generate_v5(%s::uuid, %s)::text"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, (str(namespace), name))
        row = await cur.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_post_key_id_matches_python():
    key = PostKey(organization_id=_ORGANIZATION, role_id="mayor", division_ocdid=_DIVISION)

    sql = await _uuid5(POST_NAMESPACE, f"{_ORGANIZATION}|mayor|{_DIVISION}")

    assert sql == key.post_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_membership_id_matches_python():
    post_id = str(uuid.uuid4())

    sql = await _uuid5(MEMBERSHIP_NAMESPACE, f"{_PERSON}|{post_id}")

    assert sql == membership_id(_PERSON, post_id)


_MIGRATIONS = sorted(
    (Path(__file__).parents[3] / "database_operations/migrations").glob("*.up.sql")
)


@pytest.mark.integration
@pytest.mark.parametrize(
    "function, namespace",
    [("pg_temp.post_key_id", POST_NAMESPACE), ("pg_temp.membership_id", MEMBERSHIP_NAMESPACE)],
)
def test_the_migrations_use_the_same_namespaces(function, namespace):
    """The migrations spell the namespaces as literals, since SQL cannot import Python."""
    defining = [
        path for path in _MIGRATIONS if f"FUNCTION {function}" in path.read_text()
    ]

    assert defining
    for path in defining:
        assert str(namespace) in path.read_text(), path.name
