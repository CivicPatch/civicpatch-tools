"""Database queries for roster comparisons: saved runs, their jurisdictions and their people."""

import json

from psycopg.rows import dict_row

from database.database import get_pool
from schemas.roster_comparisons import (
    ComparedField,
    FieldLevel,
    JurisdictionComparison,
    JurisdictionRates,
    PersonComparison,
    PersonOutcome,
    RosterComparison,
    RosterComparisonListRow,
    RosterComparisonRun,
    RunJurisdiction,
    RunOrganization,
    RunPerson,
)

_STARTED_AT = """to_char(roster_comparison_runs.started_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'"""

# A person counts unless civicpatch-only in none of %(organizations)s; one saved before
# organizations were kept (none listed) always counts.
_COMPARED = """(
    roster_comparison_people.outcome <> 'only_in_civicpatch'

    OR jsonb_array_length(
        coalesce(
            roster_comparison_people.comparison -> 'organizations',
            '[]'::jsonb
        )
    ) = 0

    OR roster_comparison_people.comparison -> 'organizations'
        ?| %(organizations)s::text[]
)"""

# Each column aliased to the model's field, so reading the row needs no second list to keep in step.
_RUN_COLUMNS = f"""
    id::text AS id, state, started_by_user_id::text AS started_by_user_id,
    {_STARTED_AT} AS started_at,
    source_columns, corrections, rates, jurisdictions_not_named
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
            (state, started_by_user_id, source_columns, corrections, rates,
             jurisdictions_not_named)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id::text
        """,
        (
            comparison.state,
            started_by_user_id,
            json.dumps(comparison.source_columns),
            json.dumps(comparison.corrections),
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


async def get_roster_comparison_organizations(run_id: str) -> list[RunOrganization]:
    """Only matched and civicpatch-only people carry organizations, so every row counted is civicpatch's."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT organization AS name,
                   count(DISTINCT jurisdiction_ocdid) AS jurisdictions,
                   count(*) FILTER (WHERE outcome = 'matched') AS matched,
                   count(*) AS civicpatch_people
            FROM roster_comparison_people,
                 jsonb_array_elements_text(comparison -> 'organizations') AS organization
            WHERE run_id = %s
            GROUP BY organization
            ORDER BY matched DESC, organization
            """,
            (run_id,),
        )
        rows = await cur.fetchall()
    return [RunOrganization.model_validate(row) for row in rows]


_IN_RUN = """EXISTS (
    SELECT 1
    FROM roster_comparison_jurisdictions
    WHERE roster_comparison_jurisdictions.run_id = %(run_id)s
      AND roster_comparison_jurisdictions.jurisdiction_ocdid = jurisdictions.jurisdiction_ocdid
)"""


async def get_roster_comparison_run_jurisdictions(
    run_id: str, state: str, compared: bool | None
) -> list[RunJurisdiction]:
    """The run's jurisdictions and the state's other active ones, by name; `compared` keeps only
    one kind. The state's others are the saved `jurisdictions_not_named` count, listed."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            f"""
            SELECT *
            FROM (
                SELECT jurisdictions.jurisdiction_ocdid,
                       coalesce(
                           jurisdictions.data ->> 'display_name',
                           jurisdictions.data ->> 'name',
                           jurisdictions.jurisdiction_ocdid
                       ) AS name,
                       {_IN_RUN} AS compared
                FROM jurisdictions
                WHERE (jurisdictions.state = %(state)s AND jurisdictions.status = 'active')
                   OR {_IN_RUN}
            ) AS run_jurisdictions
            WHERE %(compared)s::boolean IS NULL OR run_jurisdictions.compared = %(compared)s
            ORDER BY run_jurisdictions.name, run_jurisdictions.jurisdiction_ocdid
            """,
            {"run_id": run_id, "state": state, "compared": compared},
        )
        rows = await cur.fetchall()
    return [RunJurisdiction.model_validate(row) for row in rows]


async def count_roster_comparison_not_compared(run_id: str, organizations: list[str]) -> dict[str, int]:
    """Per jurisdiction, the civicpatch-only people in none of `organizations`."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT jurisdiction_ocdid, count(*) FROM roster_comparison_people
            WHERE run_id = %(run_id)s AND NOT {_COMPARED}
            GROUP BY jurisdiction_ocdid
            """,
            {"run_id": run_id, "organizations": organizations},
        )
        rows = await cur.fetchall()
    return {ocdid: count for ocdid, count in rows}


async def get_roster_comparison_people(
    run_id: str, jurisdiction_ocdid: str, organizations: list[str]
) -> list[PersonComparison]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT comparison FROM roster_comparison_people
            WHERE run_id = %(run_id)s AND jurisdiction_ocdid = %(ocdid)s AND {_COMPARED}
            ORDER BY position
            """,
            {"run_id": run_id, "ocdid": jurisdiction_ocdid, "organizations": organizations},
        )
        rows = await cur.fetchall()
    return [PersonComparison.model_validate(row[0]) for row in rows]


async def get_roster_comparison_people_page(
    run_id: str,
    outcome: PersonOutcome | None,
    field: ComparedField | None,
    levels: list[FieldLevel],
    organizations: list[str],
    limit: int,
    offset: int,
) -> tuple[int, list[RunPerson]]:
    """One page of a run's compared people across every jurisdiction, and their total. Each filter
    applies only when given; `levels` are the ones `field` must have graded at."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT jurisdiction_ocdid, comparison, count(*) OVER ()
            FROM roster_comparison_people
            WHERE run_id = %(run_id)s AND {_COMPARED}
              AND (%(outcome)s::text IS NULL OR outcome = %(outcome)s)
              AND (%(field)s::text IS NULL OR comparison -> 'fields' -> %(field)s ->> 'level' = ANY(%(levels)s::text[]))
            ORDER BY jurisdiction_ocdid, position
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {
                "run_id": run_id,
                "outcome": outcome.value if outcome else None,
                "field": field.value if field else None,
                "levels": [level.value for level in levels],
                "organizations": organizations,
                "limit": limit,
                "offset": offset,
            },
        )
        rows = await cur.fetchall()
    total = rows[0][2] if rows else 0
    return total, [
        RunPerson(jurisdiction_ocdid=ocdid, person=PersonComparison.model_validate(comparison))
        for ocdid, comparison, _ in rows
    ]
