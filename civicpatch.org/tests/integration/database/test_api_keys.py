"""`api_keys` against real Postgres: a minted key, looked up by its secret, carries its scope;
the owner's listing shows its scope and label.

Isolation: a dedicated user, whose keys are deleted before and after each test.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.users import create_api_key, get_api_keys_for_user, get_user_by_api_key, touch_api_key
from schemas.common import ApiKeyScope

_USER_EMAIL = "api-key-tests@civicpatch.test"


async def _user_id() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (email, provider, provider_user_id, username, role)
            VALUES (%s, 'test', %s, 'api-key-tests', 'maintainers')
            ON CONFLICT (provider, provider_user_id) DO UPDATE SET email = EXCLUDED.email
            RETURNING id::text
            """,
            (_USER_EMAIL, _USER_EMAIL),
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row is not None
    return row[0]


async def _wipe(user_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM api_keys WHERE user_id = %s", (user_id,))
        await conn.commit()


@pytest_asyncio.fixture
async def user_id():
    user = await _user_id()
    await _wipe(user)
    yield user
    await _wipe(user)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("scope", list(ApiKeyScope))
async def test_a_key_is_looked_up_with_its_scope(user_id: str, scope: ApiKeyScope):
    api_key = await create_api_key("test", _USER_EMAIL, scope, "laptop")
    [listed] = await get_api_keys_for_user("test", _USER_EMAIL)

    user = await get_user_by_api_key(api_key)

    assert user is not None
    assert user["id"] == user_id
    assert user["key_scope"] == scope.value
    assert user["key_id"] == listed["id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_listing_shows_scope_and_label(user_id: str):
    await create_api_key("test", _USER_EMAIL, ApiKeyScope.FULL, "sheet push")

    [key] = await get_api_keys_for_user("test", _USER_EMAIL)

    assert key["scope"] == ApiKeyScope.FULL.value
    assert key["label"] == "sheet push"


async def _age_last_use(user_id: str, minutes: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE api_keys SET last_used_at = now() - make_interval(mins => %s) WHERE user_id = %s",
            (minutes, user_id),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_key_is_marked_used_at_most_once_a_minute(user_id: str):
    await create_api_key("test", _USER_EMAIL, ApiKeyScope.AGENT, "laptop")
    [key] = await get_api_keys_for_user("test", _USER_EMAIL)
    assert key["last_used_at"] is None

    await touch_api_key(key["id"])
    [first] = await get_api_keys_for_user("test", _USER_EMAIL)
    await touch_api_key(key["id"])
    [second] = await get_api_keys_for_user("test", _USER_EMAIL)

    assert first["last_used_at"] is not None
    assert second["last_used_at"] == first["last_used_at"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_key_last_used_over_a_minute_ago_is_marked_again(user_id: str):
    await create_api_key("test", _USER_EMAIL, ApiKeyScope.AGENT, "laptop")
    [key] = await get_api_keys_for_user("test", _USER_EMAIL)
    await _age_last_use(user_id, 2)
    [aged] = await get_api_keys_for_user("test", _USER_EMAIL)

    await touch_api_key(key["id"])
    [touched] = await get_api_keys_for_user("test", _USER_EMAIL)

    assert touched["last_used_at"] > aged["last_used_at"]
