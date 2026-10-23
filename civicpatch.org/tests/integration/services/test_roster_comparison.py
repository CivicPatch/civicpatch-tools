"""`run_roster_comparison` against real Postgres: an upload read against seeded rosters and saved.

Isolation: sentinel state 'zr' and a dedicated user, wiped before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from database.database import get_pool
from database.roster_comparisons import get_roster_comparison_people, get_roster_comparison_run
from schemas.roster_comparisons import PersonOutcome, RosterComparisonHeader, RosterComparisonUpload, UploadedRow
from services.roster_comparison import run_roster_comparison
from services.roster_comparison_drafts import (
    DraftIsEmpty,
    DraftNotFound,
    add_draft_rows,
    finish_draft,
    start_draft,
)
from tests.integration import factories

_BARRE = "ocd-jurisdiction/country:us/state:zr/place:zr_barre/government"
_STOWE = "ocd-jurisdiction/country:us/state:zr/place:zr_stowe/government"
_RUTLAND = "ocd-jurisdiction/country:us/state:zr/place:zr_rutland/government"
_JURISDICTIONS = [_BARRE, _STOWE, _RUTLAND]
_DIVISION = "ocd-division/country:us/state:zr/place:zr_barre"
_USER_EMAIL = "roster-comparison-service@civicpatch.test"
_JANE = str(uuid.uuid5(uuid.NAMESPACE_URL, "roster-comparison-service/jane"))


async def _wipe() -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM roster_comparison_runs r USING users u WHERE r.started_by_user_id = u.id AND u.email = %s",
            (_USER_EMAIL,),
        )
        await cur.execute(
            "DELETE FROM roster_comparison_drafts d USING users u WHERE d.owner_user_id = u.id AND u.email = %s",
            (_USER_EMAIL,),
        )
        await cur.execute(
            "DELETE FROM memberships m USING posts p WHERE m.post_id = p.id AND p.jurisdiction_ocdid = ANY(%s)",
            (_JURISDICTIONS,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(f"DELETE FROM {table} WHERE jurisdiction_ocdid = ANY(%s)", (_JURISDICTIONS,))
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zr'")
        await conn.commit()


async def _seed() -> str:
    """Three jurisdictions; Jane Doe seated in Barre. Returns the user id."""
    for ocdid in _JURISDICTIONS:
        await factories.seed_jurisdiction(ocdid, "zr")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO divisions (ocdid, jurisdiction_ocdid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (_DIVISION, _BARRE),
        )
        organization_id = await factories.default_organization(cur, _BARRE)
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, 'Jane Doe')", (_JANE, _BARRE)
        )
        post_id = await factories.seed_post(cur, _BARRE, organization_id, "member", _DIVISION)
        await factories.bind_membership(
            cur, factories.SeededMembership(person_id=_JANE), post_id, organization_id,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        await cur.execute(
            """
            INSERT INTO users (email, provider, provider_user_id, username, role)
            VALUES (%s, 'test', %s, 'roster-comparison-service', 'maintainers')
            ON CONFLICT (provider, provider_user_id) DO UPDATE SET email = EXCLUDED.email
            RETURNING id::text
            """,
            (_USER_EMAIL, _USER_EMAIL),
        )
        row = await cur.fetchone()
        await conn.commit()
    assert row is not None
    return row[0]


@pytest_asyncio.fixture
async def user_id():
    await _wipe()
    yield await _seed()
    await _wipe()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_upload_is_compared_per_jurisdiction_and_saved(user_id):
    upload = RosterComparisonUpload(
        state="zr",
        source_columns={"name": ["Official"], "jurisdiction_ocdid": ["Town"]},
        corrections=["2 names reordered from 'Last, First'"],
        rows=[
            {"source_row": 2, "jurisdiction_ocdid": _BARRE, "name": "Jane Doe"},
            {"source_row": 3, "jurisdiction_ocdid": _STOWE, "name": "Lee Park"},
            {"source_row": 4, "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:zr/place:zr_nowhere/government", "name": "Ann Lee"},
        ],
    )

    run_id = await run_roster_comparison(upload, user_id)

    run = await get_roster_comparison_run(run_id)
    assert run is not None
    assert (run.rates.outcomes.matched, run.rates.outcomes.only_in_uploaded_data) == (1, 1)
    assert [row.source_row for row in run.rejected] == [4]
    assert run.jurisdictions_not_named == 1
    [jane] = await get_roster_comparison_people(run_id, _BARRE)
    assert (jane.outcome, jane.person_id) == (PersonOutcome.MATCHED, _JANE)


_HEADER = RosterComparisonHeader(state="zr", source_columns={"name": ["Official"]}, corrections=[])


def _rows(*rows: dict) -> list[UploadedRow]:
    return [UploadedRow.model_validate(row) for row in rows]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_draft_sent_in_batches_becomes_the_same_run_and_is_gone(user_id):
    draft = await start_draft(_HEADER, user_id)
    await add_draft_rows(draft.id, _rows({"source_row": 2, "jurisdiction_ocdid": _BARRE, "name": "Jane Doe"}), user_id)
    second = await add_draft_rows(
        draft.id, _rows({"source_row": 3, "jurisdiction_ocdid": _STOWE, "name": "Lee Park"}), user_id
    )
    assert second.rows == 2

    created = await finish_draft(draft.id, user_id)

    run = await get_roster_comparison_run(created.id)
    assert run is not None
    assert (run.rates.outcomes.matched, run.rates.outcomes.only_in_uploaded_data) == (1, 1)
    with pytest.raises(DraftNotFound):
        await finish_draft(draft.id, user_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_someone_elses_draft_is_not_found(user_id):
    draft = await start_draft(_HEADER, user_id)

    with pytest.raises(DraftNotFound):
        await add_draft_rows(
            draft.id, _rows({"source_row": 2, "jurisdiction_ocdid": _BARRE, "name": "Jane Doe"}), str(uuid.uuid4())
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_empty_draft_cannot_be_finished(user_id):
    draft = await start_draft(_HEADER, user_id)

    with pytest.raises(DraftIsEmpty):
        await finish_draft(draft.id, user_id)
