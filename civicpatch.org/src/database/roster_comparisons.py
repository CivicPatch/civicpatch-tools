"""Database queries for roster comparisons: saved runs, their jurisdictions and their people."""

import json

from psycopg.rows import dict_row

from database.database import get_pool
from schemas.roster_comparisons import (
    ComparedField,
    FieldLevel,
    FieldPerson,
    JurisdictionComparison,
    JurisdictionRates,
    PersonComparison,
    RosterComparison,
    RosterComparisonListRow,
    RosterComparisonRun,
)

_STARTED_AT = """to_char(roster_comparison_runs.started_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'"""

# Each column aliased to the model's field, so reading the row needs no second list to keep in step.
_RUN_COLUMNS = f"""
    id::text AS id, state, started_by_user_id::text AS started_by_user_id,
    {_STARTED_AT} AS started_at,
    source_columns, corrections, rejected, rates, jurisdictions_not_named
"""


async def insert_roster_comparison(started_by_user_id: str, comparison: RosterComparison) -> str:
    """The run, its jurisdictions and its people, in one transaction. Returns the run id."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        run_id = await _insert_run(cur, started_by_user_id, comparison)
        await _insert_jurisdictions(cur, run_id, comparison.jurisdictions)
        await _insert_people(cur, run_id, comparison.jurisdictions)
        await conn.commit()
    return run_id


async def _insert_run(cur, started_by_user_id: str, comparison: RosterComparison) -> str:
    await cur.execute(
        """
        INSERT INTO roster_comparison_runs
            (state, started_by_user_id, source_columns, corrections, rejected, rates,
             jurisdictions_not_named)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id::text
        """,
        (
            comparison.state,
            started_by_user_id,
            json.dumps(comparison.source_columns),
            json.dumps(comparison.corrections),
            json.dumps([row.model_dump(mode="json") for row in comparison.rejected]),
            comparison.rates.model_dump_json(),
            comparison.jurisdictions_not_named,
        ),
    )
    row = await cur.fetchone()
    assert row is not None  # RETURNING always yields the inserted row
    return row[0]


async def _insert_jurisdictions(cur, run_id: str, jurisdictions: list[JurisdictionComparison]) -> None:
    await cur.executemany(
        """
        INSERT INTO roster_comparison_jurisdictions (run_id, jurisdiction_ocdid, rates)
        VALUES (%s, %s, %s)
        """,
        [(run_id, j.jurisdiction_ocdid, j.rates.model_dump_json()) for j in jurisdictions],
    )


async def _insert_people(cur, run_id: str, jurisdictions: list[JurisdictionComparison]) -> None:
    await cur.executemany(
        """
        INSERT INTO roster_comparison_people
            (run_id, jurisdiction_ocdid, position, outcome, source_row, person_id, comparison)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                run_id,
                jurisdiction.jurisdiction_ocdid,
                position,
                person.outcome.value,
                person.uploaded.source_row if person.uploaded else None,
                person.person_id,
                person.model_dump_json(),
            )
            for jurisdiction in jurisdictions
            for position, person in enumerate(jurisdiction.people)
        ],
    )


async def get_roster_comparison_run(run_id: str) -> RosterComparisonRun | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(f"SELECT {_RUN_COLUMNS} FROM roster_comparison_runs WHERE id = %s", (run_id,))
        row = await cur.fetchone()
    return None if row is None else RosterComparisonRun.model_validate(row)


async def get_roster_comparison_runs(limit: int, offset: int) -> tuple[int, list[RosterComparisonListRow]]:
    """One page of saved runs, newest first, and how many there are."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            f"""
            SELECT
                roster_comparison_runs.id::text AS id,
                roster_comparison_runs.state,
                {_STARTED_AT} AS started_at,
                users.username AS started_by,
                (
                    SELECT count(*) FROM roster_comparison_jurisdictions
                    WHERE roster_comparison_jurisdictions.run_id = roster_comparison_runs.id
                )::int AS jurisdictions_named,
                roster_comparison_runs.rates,
                count(*) OVER () AS total
            FROM roster_comparison_runs
            JOIN users ON users.id = roster_comparison_runs.started_by_user_id
            ORDER BY roster_comparison_runs.started_at DESC, roster_comparison_runs.id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = await cur.fetchall()
    total = rows[0]["total"] if rows else 0
    return total, [RosterComparisonListRow.model_validate(row) for row in rows]


async def get_roster_comparison_jurisdictions(run_id: str) -> list[JurisdictionRates]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, rates FROM roster_comparison_jurisdictions
            WHERE run_id = %s ORDER BY jurisdiction_ocdid
            """,
            (run_id,),
        )
        rows = await cur.fetchall()
    return [JurisdictionRates(jurisdiction_ocdid=ocdid, rates=rates) for ocdid, rates in rows]


async def get_roster_comparison_people(run_id: str, jurisdiction_ocdid: str) -> list[PersonComparison]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT comparison FROM roster_comparison_people
            WHERE run_id = %s AND jurisdiction_ocdid = %s ORDER BY position
            """,
            (run_id, jurisdiction_ocdid),
        )
        rows = await cur.fetchall()
    return [PersonComparison.model_validate(row[0]) for row in rows]


async def get_roster_comparison_field_people(
    run_id: str, field: ComparedField, levels: list[FieldLevel], limit: int, offset: int
) -> tuple[int, list[FieldPerson]]:
    """One page of the matched people whose `field` graded at one of `levels`, and their total."""
    level_values = [level.value for level in levels]
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, comparison, count(*) OVER ()
            FROM roster_comparison_people
            WHERE run_id = %s AND comparison -> 'fields' -> %s ->> 'level' = ANY(%s)
            ORDER BY jurisdiction_ocdid, position
            LIMIT %s OFFSET %s
            """,
            (run_id, field.value, level_values, limit, offset),
        )
        rows = await cur.fetchall()
    total = rows[0][2] if rows else 0
    return total, [
        FieldPerson(jurisdiction_ocdid=ocdid, person=PersonComparison.model_validate(comparison))
        for ocdid, comparison, _ in rows
    ]
