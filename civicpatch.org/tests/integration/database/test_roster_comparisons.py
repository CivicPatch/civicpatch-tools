"""`roster_comparison_*` against real Postgres: a run saved in one go and read back in its parts.

Isolation: a dedicated user, whose runs are deleted (and cascade) before and after each test.
"""

import pytest
import pytest_asyncio

from database.database import get_pool
from database.roster_comparisons import (
    get_roster_comparison_field_people,
    get_roster_comparison_jurisdictions,
    get_roster_comparison_people,
    get_roster_comparison_run,
    get_roster_comparison_runs,
    insert_roster_comparison,
)
from schemas.roster_comparisons import (
    ComparedField,
    ComparisonRates,
    FieldComparison,
    FieldLevel,
    JurisdictionComparison,
    OutcomeCounts,
    PersonComparison,
    PersonOutcome,
    RejectedReason,
    RejectedRow,
    RosterComparison,
    UploadedRow,
)

_USER_EMAIL = "roster-comparison-tests@civicpatch.test"
_BARRE = "ocd-jurisdiction/country:us/state:zz/place:zz_barre/government"
_STOWE = "ocd-jurisdiction/country:us/state:zz/place:zz_stowe/government"
_PERSON_ID = "11111111-1111-1111-1111-111111111111"


async def _user_id() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (email, provider, provider_user_id, username, role)
            VALUES (%s, 'test', %s, 'roster-comparison-tests', 'maintainers')
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
        await cur.execute("DELETE FROM roster_comparison_runs WHERE started_by_user_id = %s", (user_id,))
        await conn.commit()


@pytest_asyncio.fixture
async def user_id():
    user = await _user_id()
    await _wipe(user)
    yield user
    await _wipe(user)


def _matched(source_row: int, emails_level: FieldLevel) -> PersonComparison:
    return PersonComparison(
        outcome=PersonOutcome.MATCHED,
        uploaded=UploadedRow(source_row=source_row, jurisdiction_ocdid=_BARRE, name=f"Person {source_row}"),
        person_id=_PERSON_ID,
        person_name=f"Person {source_row}",
        fields={ComparedField.EMAILS: FieldComparison(level=emails_level, uploaded=["a"], civicpatch=["b"])},
    )


def _comparison() -> RosterComparison:
    barre_people = [
        _matched(2, FieldLevel.DIFFERS),
        _matched(3, FieldLevel.EQUAL),
        _matched(4, FieldLevel.DIFFERS),
        PersonComparison(outcome=PersonOutcome.ONLY_IN_CIVICPATCH, person_id=_PERSON_ID, person_name="Maria"),
    ]
    barre_rates = ComparisonRates(outcomes=OutcomeCounts(matched=3, only_in_civicpatch=1))
    return RosterComparison(
        state="zz",
        source_columns={"name": ["Official"]},
        corrections=["212 names reordered"],
        rejected=[RejectedRow(source_row=77, jurisdiction_ocdid="nowhere", reason=RejectedReason.UNKNOWN_JURISDICTION)],
        rates=barre_rates,
        jurisdictions_not_named=12,
        jurisdictions=[
            JurisdictionComparison(jurisdiction_ocdid=_BARRE, rates=barre_rates, people=barre_people),
            JurisdictionComparison(jurisdiction_ocdid=_STOWE, rates=ComparisonRates(), people=[]),
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_reads_back_in_its_parts(user_id):
    run_id = await insert_roster_comparison(user_id, _comparison())

    run = await get_roster_comparison_run(run_id)
    assert run is not None
    assert (run.state, run.started_by_user_id, run.jurisdictions_not_named) == ("zz", user_id, 12)
    assert run.corrections == ["212 names reordered"]
    assert [row.source_row for row in run.rejected] == [77]
    assert run.rates.outcomes.matched == 3

    jurisdictions = await get_roster_comparison_jurisdictions(run_id)
    assert [j.jurisdiction_ocdid for j in jurisdictions] == [_BARRE, _STOWE]

    people = await get_roster_comparison_people(run_id, _BARRE)
    assert [p.outcome for p in people] == [PersonOutcome.MATCHED] * 3 + [PersonOutcome.ONLY_IN_CIVICPATCH]
    assert people[0].uploaded is not None and people[0].uploaded.source_row == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_fields_people_page_by_level(user_id):
    run_id = await insert_roster_comparison(user_id, _comparison())

    total, page = await get_roster_comparison_field_people(
        run_id, ComparedField.EMAILS, [FieldLevel.DIFFERS], limit=1, offset=1
    )

    assert total == 2
    assert [(p.jurisdiction_ocdid, p.person.uploaded.source_row) for p in page if p.person.uploaded] == [(_BARRE, 4)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_runs_list_newest_first_with_who_ran_them(user_id):
    older = await insert_roster_comparison(user_id, _comparison())
    newer = await insert_roster_comparison(user_id, _comparison())

    total, runs = await get_roster_comparison_runs(limit=100, offset=0)

    ours = [run for run in runs if run.id in (older, newer)]
    assert [run.id for run in ours] == [newer, older]
    assert ours[0].started_by == "roster-comparison-tests"
    assert (ours[0].state, ours[0].jurisdictions_named, ours[0].rates.outcomes.matched) == ("zz", 2, 3)
    assert total >= 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_run_is_none(user_id):
    assert await get_roster_comparison_run("00000000-0000-0000-0000-000000000000") is None
