"""`roster_comparison_drafts` against real Postgres: the row cap holds across batches.

Isolation: a dedicated user whose drafts are deleted before and after each test.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.roster_comparison_drafts import (
    append_roster_comparison_draft_rows,
    insert_roster_comparison_draft,
)
from schemas.roster_comparisons import RosterComparisonHeader, UploadedRow

_USER_EMAIL = "roster-comparison-drafts@civicpatch.test"
_HEADER = RosterComparisonHeader(state="zz", source_columns={}, corrections=[])
_ROW = UploadedRow(source_row=2, jurisdiction_ocdid="ocd-jurisdiction/country:us/state:zz/place:x/government", name="Jane Doe")


async def _user_id() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (email, provider, provider_user_id, username, role)
            VALUES (%s, 'test', %s, 'roster-comparison-drafts', 'maintainers')
            ON CONFLICT (provider, provider_user_id) DO UPDATE SET email = EXCLUDED.email
            RETURNING id::text
            """,
            (_USER_EMAIL, _USER_EMAIL),
        )
        row = await cur.fetchone()
        await cur.execute("DELETE FROM roster_comparison_drafts WHERE owner_user_id = %s", (row[0],))
        await conn.commit()
    return row[0]


@pytest_asyncio.fixture
async def user_id():
    user = await _user_id()
    yield user
    await _user_id()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rows_past_the_cap_are_refused_across_batches(user_id):
    draft = await insert_roster_comparison_draft(user_id, _HEADER)

    first = await append_roster_comparison_draft_rows(draft.id, user_id, [_ROW, _ROW], max_rows=3)
    second = await append_roster_comparison_draft_rows(draft.id, user_id, [_ROW, _ROW], max_rows=3)

    assert first is not None and first.rows == 2
    assert second is None
