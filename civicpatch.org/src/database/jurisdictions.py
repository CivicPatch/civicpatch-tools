import datetime
import json
import logging
import math
from collections.abc import Mapping
from typing import List

import shared.utils.id_utils
from core.jurisdiction_search import (
    build_parent_ocdids,
    build_search_text,
)
from core.change_logs import roster_change
from database.database import get_pool, to_iso
from database.people import PERSON_JSON
from database.changesets import AVAILABLE_FOR_REVIEW, REVIEW_STATUS, RUN_IN_FLIGHT
from psycopg import sql
from schemas.common import (
    Jurisdiction,
    PeoplePipelineRunHistory,
    StateJurisdictionSets,
)
from schemas.jurisdictions import JurisdictionSearchResult
from shared.schemas import Person
from shared.utils.statuses import ChangeLogType, RequestReviewStatus

logger = logging.getLogger(__name__)

FRESH_SINCE_SQL = "now() - interval '90 days'"


def jurisdiction_rows(
    entries: list[dict[str, str]],
    state: str,
    level: str,
    updated_at,
    state_name: str | None = None,
):
    return [
        (
            entry["id"],
            state,
            level,
            json.dumps(entry),
            updated_at,
            build_search_text(entry, state, state_name),
            build_parent_ocdids(entry, state, level),
        )
        for entry in entries
    ]


# Tier 1 — exact token match with prefixes, via the FTS index. The two-argument
# to_tsvector('simple', …) must match the index expression exactly; the one-argument form
# resolves against a GUC, misses the index, and silently sequential-scans.
_SEARCH_MATCH_CLAUSE = """
    FROM jurisdictions j
    WHERE to_tsvector('simple', j.search_text) @@ to_tsquery('simple', %s)
      AND j.status = 'active'
      AND j.level = ANY(%s)
"""


# Tier 2 — trigram fallback for typos, one indexed condition per token, ANDed.
# Operand order is load-bearing: `a %> b` is word_similarity(b, a), so the indexed column
# must be on the LEFT. Reversed, it plans a sequential scan and returns nothing.
def _fuzzy_match_clause(token_count: int) -> sql.Composed:
    # Composed via psycopg.sql so only the *number* of conditions varies; every token is
    # still bound as a parameter, and nothing user-supplied reaches the SQL text.
    conditions = sql.SQL(" AND ").join([sql.SQL("j.search_text %%> %s")] * token_count)
    return sql.SQL(
        """
        FROM jurisdictions j
        WHERE {conditions}
          AND j.status = 'active'
          AND j.level = ANY(%s)
        """
    ).format(conditions=conditions)


_SEARCH_SELECT_LIST = """
    SELECT
        j.jurisdiction_ocdid,
        j.level,
        j.data->>'name',
        j.data->>'display_name',
        (j.data->>'population')::bigint,
        -- Names resolved here rather than stored, so a renamed parent is correct
        -- immediately. Which parents, and their order, was settled at sync time.
        (SELECT array_agg(parent_row.data->>'name' ORDER BY parent.ord)
           FROM unnest(j.parent_ocdids) WITH ORDINALITY AS parent(ocdid, ord)
           JOIN jurisdictions parent_row
             ON parent_row.jurisdiction_ocdid = parent.ocdid)
"""

# jurisdiction_ocdid breaks ties so paging is stable: without a total order a row can
# appear on two pages or none.
_SEARCH_ORDER = """
    ORDER BY (j.data->>'population')::bigint DESC NULLS LAST, j.jurisdiction_ocdid
    LIMIT %s OFFSET %s;
"""

# Counted separately rather than with count(*) OVER (): a window count only rides back
# attached to rows, so a page past the end would report a total of 0.
_SEARCH_COUNT_QUERY = f"SELECT count(*) {_SEARCH_MATCH_CLAUSE};"
_SEARCH_QUERY = f"{_SEARCH_SELECT_LIST}{_SEARCH_MATCH_CLAUSE}{_SEARCH_ORDER}"


def _fuzzy_count_query(token_count: int) -> sql.Composed:
    return sql.SQL("SELECT count(*) {}").format(_fuzzy_match_clause(token_count))


def _fuzzy_page_query(token_count: int) -> sql.Composed:
    # Ordered by population like tier 1, not by similarity: every hit already cleared the
    # same threshold on every token, so there is no meaningful gradient left between them,
    # and a stable total order is what keeps paging coherent.
    return sql.SQL("{select}{match}{order}").format(
        select=sql.SQL(_SEARCH_SELECT_LIST),
        match=_fuzzy_match_clause(token_count),
        order=sql.SQL(_SEARCH_ORDER),
    )


def _search_result(row) -> JurisdictionSearchResult:
    return JurisdictionSearchResult(
        jurisdiction_ocdid=row[0],
        level=row[1],
        name=row[2],
        display_name=row[3],
        population=row[4],
        parent_names=row[5] or [],
    )


async def search_jurisdictions_by_text(
    tsquery: str, levels: list[str], limit: int, skip: int = 0
) -> tuple[int, list[JurisdictionSearchResult]]:
    # levels must be a list, not any Sequence: psycopg adapts only list to a PG array —
    # a tuple becomes a composite ("malformed array literal") and a set cannot adapt.
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(_SEARCH_COUNT_QUERY, (tsquery, levels))
        count_row = await cur.fetchone()
        total_items = count_row[0] if count_row else 0

        await cur.execute(_SEARCH_QUERY, (tsquery, levels, limit, skip))
        results = await cur.fetchall()

    return total_items, [_search_result(row) for row in results]


async def search_jurisdictions_fuzzy(
    tokens: list[str], levels: list[str], limit: int, skip: int = 0
) -> tuple[int, list[JurisdictionSearchResult]]:
    if not tokens:
        return 0, []

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(_fuzzy_count_query(len(tokens)), (*tokens, levels))
        count_row = await cur.fetchone()
        total_items = count_row[0] if count_row else 0

        await cur.execute(
            _fuzzy_page_query(len(tokens)), (*tokens, levels, limit, skip)
        )
        results = await cur.fetchall()

    return total_items, [_search_result(row) for row in results]


async def get_states_with_names() -> list[dict[str, str]]:
    # The level='state' rows ARE the state list — they sync from open-data like every
    # other jurisdiction, which is what lets shared/config/states.yml go away.
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT state, data->>'name'
            FROM jurisdictions
            WHERE level = 'state' AND status = 'active'
            ORDER BY data->>'name';
            """,
        )
        results = await cur.fetchall()

    return [{"code": code, "name": name} for code, name in results if code and name]


async def get_state_names() -> dict[str, str]:
    # For search_text, which embeds the state's display name. Safe to read mid-sync
    # because level_ordered_batches stores the state group first.
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT state, data->>'name'
            FROM jurisdictions
            WHERE level = 'state' AND status = 'active';
            """,
        )
        results = await cur.fetchall()

    return {state: name for state, name in results if state and name}


async def get_states() -> List[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT state from jurisdictions
            ORDER by state;
            """,
        )
        results = await cur.fetchall()
        unique_states = [row[0] for row in results]

    return unique_states


async def get_jurisdiction(jurisdiction_ocdid: str, with_geom: bool = False):
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            if with_geom:
                await cur.execute(
                    """
                    SELECT
                        j.data,
                        ST_X(ST_Centroid(g.geom)) AS lon,
                        ST_Y(ST_Centroid(g.geom)) AS lat,
                        j.scraped_at
                    FROM jurisdictions j
                    LEFT JOIN geo g ON j.data->>'geoid' = g.geoid
                    WHERE j.jurisdiction_ocdid = %s AND j.status = 'active'
                    LIMIT 1;
                    """,
                    (jurisdiction_ocdid,),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                data, lon, lat, scraped_at = row[0], row[1], row[2], row[3]
                center = (
                    {"lat": float(lat), "lng": float(lon)}
                    if lon is not None and lat is not None
                    else None
                )
                return {
                    "data": data,
                    "geo_center": center,
                    "scraped_at": to_iso(scraped_at),
                }
            else:
                await cur.execute(
                    """
                    SELECT data, scraped_at FROM jurisdictions
                    WHERE jurisdiction_ocdid = %s AND status = 'active'
                    LIMIT 1;
                    """,
                    (jurisdiction_ocdid,),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                # scraped_at is DB metadata, not an open-data field, so it rides beside
                # `data` rather than being folded into it.
                return {"data": row[0], "scraped_at": to_iso(row[1])}
    except Exception:
        logger.exception("Error in get_jurisdiction")
        return None


async def get_jurisdiction_geom(jurisdiction_ocdid: str):
    print("trying to find geom for", jurisdiction_ocdid)
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT ST_AsGeoJSON(g.geom)::json FROM geo g
                JOIN jurisdictions j ON j.data->>'geoid' = g.geoid
                WHERE j.jurisdiction_ocdid = %s
                LIMIT 1
                """,
                (jurisdiction_ocdid,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return row[0]
    except Exception:
        logger.exception("Error in get_jurisdiction_geom")
        return None


async def get_people_by_geo(lat: float, long: float):
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT j.jurisdiction_ocdid, j.data, {PERSON_JSON}
                FROM geo g
                JOIN jurisdictions j ON j.data->>'geoid' = g.geoid
                JOIN people ON people.jurisdiction_ocdid = j.jurisdiction_ocdid
                WHERE ST_Intersects(g.geom, ST_SetSRID(ST_Point(%s, %s), 4326))
                """,
                (long, lat),
            )
            rows = await cur.fetchall()
            if not rows:
                return {"jurisdiction_ocdid": "", "people": []}

            first_jurisdiction = rows[0][0]
            people_list = []
            for jurisdiction_ocdid, _jurisdiction_data, person_json in rows:
                try:
                    person_obj = Person(**person_json)
                except Exception:
                    person_obj = person_json
                people_list.append(person_obj)

            return {"jurisdiction_ocdid": first_jurisdiction, "people": people_list}
    except Exception:
        logger.exception("Error in get_people_by_geo")
        return []


async def get_geojson_by_latlong(lat: float, long: float, zoom: int | None = None):
    pool = await get_pool()
    if zoom is None:
        buffer_m = 1000.0
        simplify_tolerance = 0.01
        result_limit = 100
        exaggerate_buffer = 0
    else:
        meters_per_pixel = 156543.03392 * math.cos(math.radians(lat)) / (2**zoom)
        buffer_m = max(50.0, meters_per_pixel * 512.0)
        if zoom < 7:
            simplify_tolerance = 0.05
            result_limit = 20
            exaggerate_buffer = 5000
        elif zoom < 10:
            simplify_tolerance = 0.01
            result_limit = 50
            exaggerate_buffer = 1000
        else:
            simplify_tolerance = 0.001
            result_limit = 100
            exaggerate_buffer = 0

    try:
        meters_per_deg_lat = 110574.0
        meters_per_deg_lon = 111320.0 * math.cos(math.radians(lat))
        dlat = buffer_m / meters_per_deg_lat
        dlon = buffer_m / meters_per_deg_lon

        min_lon = long - dlon
        max_lon = long + dlon
        min_lat = lat - dlat
        max_lat = lat + dlat

        async with pool.connection() as conn, conn.cursor() as cur:
            geom_expr = (
                "ST_Simplify(ST_Buffer(g.geom::geography, %s)::geometry, %s)"
                if exaggerate_buffer > 0
                else "ST_Simplify(g.geom, %s)"
            )
            await cur.execute(
                f"""
                SELECT
                    j.jurisdiction_ocdid,
                    g.geoid,
                    ST_AsGeoJSON(
                        {geom_expr}
                    )::json AS geojson,
                    ST_Distance(
                        g.geom::geography,
                        ST_SetSRID(ST_Point(%s, %s), 4326)::geography
                    ) AS distance_m
                FROM geo g
                JOIN jurisdictions j ON j.data->>'geoid' = g.geoid
                WHERE g.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                  AND ST_DWithin(
                    g.geom::geography,
                    ST_SetSRID(ST_Point(%s, %s), 4326)::geography,
                    %s
                  )
                ORDER BY distance_m
                LIMIT %s;
                """,
                (
                    exaggerate_buffer,
                    simplify_tolerance if exaggerate_buffer > 0 else simplify_tolerance,
                    long,
                    lat,
                    min_lon,
                    min_lat,
                    max_lon,
                    max_lat,
                    long,
                    lat,
                    buffer_m,
                    result_limit,
                )
                if exaggerate_buffer > 0
                else (
                    simplify_tolerance,
                    long,
                    lat,
                    min_lon,
                    min_lat,
                    max_lon,
                    max_lat,
                    long,
                    lat,
                    buffer_m,
                    result_limit,
                ),
            )
            rows = await cur.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "jurisdiction_ocdid": row[0],
                        "geoid": row[1],
                        "geojson": row[2],
                        "distance_m": row[3],
                    }
                )

            return {"results": results, "buffer_m": buffer_m}
    except Exception:
        logger.exception("Error in get_geojson_by_latlong")
        return {"results": [], "buffer_m": buffer_m if "buffer_m" in locals() else None}


async def search_jurisdictions(
    state: str, search_string="", limit: int = 100, skip: int = 0
):
    if limit <= 0:
        limit = 100

    where_clauses: list[sql.Composable] = [
        sql.SQL("state = %s"),
        sql.SQL("status = 'active'"),
        sql.SQL("level = 'local'"),
    ]
    params = [state.lower()]

    if search_string:
        where_clauses.append(sql.SQL("LOWER(data->>'name') LIKE %s"))
        params.append(f"%{search_string.lower()}%")

    where_condition = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(where_clauses))

    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                sql.SQL("SELECT COUNT(*) FROM jurisdictions {};").format(
                    where_condition
                ),
                params,
            )
            count_row = await cur.fetchone()
            total_count = count_row[0] if count_row is not None else 0

            await cur.execute(
                sql.SQL("""
                SELECT jurisdiction_ocdid, data
                FROM jurisdictions
                {}
                ORDER BY jurisdiction_ocdid
                LIMIT %s OFFSET %s;
                """).format(where_condition),
                (*params, limit, skip),
            )

            results = await cur.fetchall()

            jurisdictions = []
            for row in results:
                jurisdictions.append(
                    {
                        "jurisdiction_ocdid": row[0],
                        "jurisdiction_path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(
                            row[0]
                        ),
                        **row[1],
                    }
                )

            return total_count, jurisdictions

    except Exception:
        logger.exception("Database error in get_jurisdictions")
        return 0, []


async def get_jurisdictions_by_ocdids(ocdids: list[str]) -> list[dict]:
    if not ocdids:
        return []
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid,
                   data->>'name' AS name,
                   data->>'url' AS url
            FROM jurisdictions
            WHERE jurisdiction_ocdid = ANY(%s)
            ORDER BY data->>'name'
            """,
            (ocdids,),
        )
        rows = await cur.fetchall()
        return [
            {
                "ocdid": row[0],
                "name": row[1],
                "slug": shared.utils.id_utils.jurisdiction_ocdid_to_folder(row[0]),
                "url": row[2],
            }
            for row in rows
        ]


# A dismissal whose `close_review` log carries no reason. Rendered as-is rather than guessed at
# from `status`: 32 dev rows have no reason and 7 say `discarded`, which is not in the enum.
UNKNOWN_OUTCOME = "unknown"

# What counts as a change to the roster. Review lifecycle (`merge_review`, `close_review`) and
# role taxonomy are deliberately out: they say what happened to the *review*, not to the people.
ROSTER_CHANGE_TYPES = [
    ChangeLogType.ADD_PERSON,
    ChangeLogType.EDIT_PERSON,
    ChangeLogType.DELETE_PERSON,
    ChangeLogType.ADD_POST,
    ChangeLogType.EDIT_POST,
    ChangeLogType.DELETE_POST,
    ChangeLogType.ASSIGN_MEMBERSHIP,
    ChangeLogType.ASSERT_FIELD,
]


async def get_jurisdiction_history(
    jurisdiction_ocdid,
) -> List[PeoplePipelineRunHistory]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            WITH roster_changes AS (
                SELECT cl.changeset_id,
                       jsonb_agg(jsonb_build_object(
                           'type', cl.type,
                           'created_at', cl.created_at,
                           'changes', cl.changes
                       ) ORDER BY cl.created_at) AS changes
                FROM change_logs cl
                WHERE cl.type = ANY(%s)
                  AND cl.changeset_id IN (
                      SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s
                  )
                GROUP BY cl.changeset_id
            ),
            close_reasons AS (
                SELECT DISTINCT ON (cl.changeset_id)
                       cl.changeset_id,
                       cl.changes->>'reason' AS reason
                FROM change_logs cl
                WHERE cl.type = %s
                  AND cl.changeset_id IN (
                      SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s
                  )
                ORDER BY cl.changeset_id, cl.created_at DESC
            )
            SELECT r.id::text,
                   r.created_at,
                   r.sourced_at,
                   r.status, r.progress, r.change_url, {REVIEW_STATUS},
                   r.kind,
                   r.published_at,
                   {RUN_IN_FLIGHT} AS is_running,
                   {AVAILABLE_FOR_REVIEW} AS awaiting_review,
                   CASE
                       WHEN r.published_at IS NOT NULL THEN '{RequestReviewStatus.PUBLISHED.value}'
                       WHEN r.dismissed_at IS NOT NULL
                           THEN COALESCE(cr.reason, '{UNKNOWN_OUTCOME}')
                       ELSE '{RequestReviewStatus.PENDING.value}'
                   END AS outcome,
                   resolver.display_name AS resolved_by,
                   COALESCE(rc.changes, '[]'::jsonb) AS changes
            FROM changesets r
            LEFT JOIN close_reasons cr ON cr.changeset_id = r.id::text
            LEFT JOIN users resolver ON resolver.id = r.resolved_by_user_id
            LEFT JOIN roster_changes rc ON rc.changeset_id = r.id::text
            WHERE r.jurisdiction_ocdid = %s
            ORDER BY r.created_at DESC;
            """,
            # No kind filter. It used to read `= ANY(['people','jurisdiction_manual_edit'])`,
            # which was every value the column could hold — a no-op wearing the shape of a
            # filter. The timeline wants everything that happened to this jurisdiction.
            (
                ROSTER_CHANGE_TYPES,
                jurisdiction_ocdid,
                ChangeLogType.CLOSE_REVIEW,
                jurisdiction_ocdid,
                jurisdiction_ocdid,
            ),
        )
        rows = await cur.fetchall()
        history = []
        for row in rows:
            branch_name = shared.utils.id_utils.make_job_branch(
                jurisdiction_ocdid, row[0]
            )
            history.append(
                {
                    "changeset_id": row[0],
                    "created_at": to_iso(row[1]),
                    "updated_at": to_iso(row[2]),
                    "pipeline_run_status": row[3],
                    "pipeline_run_progress": row[4],
                    "change_url": row[5],
                    "review_status": row[6],
                    "kind": row[7],
                    # When a *person* published it, not when the machine finished. The header
                    # used the run's created_at, so it dated the scrape rather than the
                    # decision.
                    "published_at": to_iso(row[8]),
                    # Told, not inferred: the page used to test the raw status against a
                    # terminal set it kept its own copy of.
                    "is_running": row[9],
                    # The pool's own definition, not a second one. `review_status` is `pending`
                    # from the moment a request exists, so a scrape still running read as
                    # awaiting review and offered a button for a roster it had not produced.
                    "awaiting_review": row[10],
                    "outcome": row[11],
                    "resolved_by": row[12],
                    "jurisdiction_ocdid": jurisdiction_ocdid,
                    "branch_name": branch_name,
                    "changes": [
                        roster_change(
                            log["type"], log["created_at"], log["changes"] or {}
                        )
                        for log in row[13]
                    ],
                }
            )
    return history


async def update_jurisdiction(jurisdiction_ocdid, state, data: dict):
    pool = await get_pool()
    async with pool.connection() as conn:
        updated_at = data.get("updated_at", None)
        if not updated_at:
            updated_at = datetime.datetime.utcnow().isoformat()
        data_json = json.dumps(data)
        print("adding jurisdiction record to db with updated_at", updated_at)
        await conn.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (jurisdiction_ocdid)
            DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at;
            """,
            (jurisdiction_ocdid, state, data_json, updated_at),
        )


async def get_jurisdiction_entry(jurisdiction_ocdid: str) -> dict | None:
    """The jurisdiction exactly as `jurisdictions.yml` carries it.

    `data` is the file entry, stored verbatim at sync time, so this is the registry's current
    state without a GitHub read.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT data FROM jurisdictions WHERE jurisdiction_ocdid = %s",
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def patch_jurisdiction_entry(
    jurisdiction_ocdid: str, patch: Mapping[str, object]
) -> None:
    """Merge a patch into the stored entry, leaving every other key alone.

    `||` rather than a whole-row write: the patch carries only what the editor sent, and an
    explicit null in it is a value to keep, not a key to drop.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE jurisdictions
               SET data = data || %s::jsonb,
                   updated_at = now()
             WHERE jurisdiction_ocdid = %s
            """,
            (json.dumps(patch), jurisdiction_ocdid),
        )


async def mark_jurisdictions_inactive(jurisdiction_ocdids: list):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            "UPDATE jurisdictions SET status = 'inactive' WHERE jurisdiction_ocdid = %s",
            [(ocdid,) for ocdid in jurisdiction_ocdids],
        )


async def bulk_update_jurisdictions(jurisdiction_records: list):
    query = """
        INSERT INTO jurisdictions
            (jurisdiction_ocdid, state, level, data, updated_at, search_text, parent_ocdids)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (jurisdiction_ocdid)
        DO UPDATE SET
            level = EXCLUDED.level,
            data = EXCLUDED.data,
            updated_at = EXCLUDED.updated_at,
            search_text = EXCLUDED.search_text,
            parent_ocdids = EXCLUDED.parent_ocdids,
            status = 'active'
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(query, jurisdiction_records)


async def deactivate_jurisdictions_not_in(
    state: str, level: str, keep_ocdids: List[str]
):
    # A jurisdiction in this (state, level) no longer in its synced jurisdictions.yml =
    # removed upstream. Each jurisdictions.yml owns exactly one (state, level) slice, so the
    # level filter keeps a state-file sync from deactivating the state's local/county rows.
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE jurisdictions SET status = 'inactive' "
            "WHERE state = %s AND level = %s AND jurisdiction_ocdid != ALL(%s)",
            (state, level, keep_ocdids),
        )


async def stamp_scraped_at(jurisdiction_ocdid: str, changeset_id: str) -> bool:
    # "Last scraped" = when the request was created, stamped when a job PR merges. Guarded on
    # `status IS NOT NULL` so a request no pipeline ran cannot blank `scraped_at` — an
    # external merge, or a roster typed in rather than scraped.
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            "UPDATE jurisdictions j SET scraped_at = r.created_at "
            "FROM changesets r "
            "WHERE r.id = %s AND r.status IS NOT NULL "
            "AND j.jurisdiction_ocdid = %s",
            (changeset_id, jurisdiction_ocdid),
        )
    return result.rowcount > 0


async def get_scraped_at(jurisdiction_ocdid: str) -> datetime.datetime | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT scraped_at FROM jurisdictions WHERE jurisdiction_ocdid = %s LIMIT 1;",
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def get_stale_jurisdictions(state: str) -> list[Jurisdiction]:
    # Stale = never scraped, or last scraped before the rolling freshness window. Only
    # active, url-bearing jurisdictions; never-scraped first.
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT j.jurisdiction_ocdid, j.data->>'name', j.data->>'url'
            FROM jurisdictions j
            WHERE j.state = %s
              AND j.status = 'active'
              AND NULLIF(j.data->>'url', '') IS NOT NULL
              AND (j.scraped_at IS NULL OR j.scraped_at < {FRESH_SINCE_SQL})
            ORDER BY j.scraped_at ASC NULLS FIRST
            """,
            (state,),
        )
        rows = await cur.fetchall()
    return [Jurisdiction(id=row[0], name=row[1], url=row[2]) for row in rows]


async def get_state_jurisdiction_sets(state: str) -> StateJurisdictionSets:
    # The per-state coverage sets: all current jurisdictions, the url-bearing subset, and
    # that subset split by freshness — covered_fresh (has officials, scraped within the
    # rolling window) vs covered_stale (has officials but aging).
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT
                j.jurisdiction_ocdid,
                NULLIF(j.data->>'url', '') IS NOT NULL AS has_url,
                (j.scraped_at IS NOT NULL AND j.scraped_at >= {FRESH_SINCE_SQL})
                    AS is_fresh,
                EXISTS (
                    SELECT 1 FROM people
                    WHERE jurisdiction_ocdid = j.jurisdiction_ocdid AND status = 'active'
                ) AS has_people
            FROM jurisdictions j
            WHERE j.state = %s AND j.status = 'active'
            """,
            (state,),
        )
        rows = await cur.fetchall()

    total: set[str] = set()
    scrapeable: set[str] = set()
    covered_fresh: set[str] = set()
    covered_stale: set[str] = set()
    for jurisdiction_ocdid, has_url, is_fresh, has_people in rows:
        total.add(jurisdiction_ocdid)
        if has_url:
            scrapeable.add(jurisdiction_ocdid)
            if has_people:
                target = covered_fresh if is_fresh else covered_stale
                target.add(jurisdiction_ocdid)
    return StateJurisdictionSets(
        total=total,
        scrapeable=scrapeable,
        covered_fresh=covered_fresh,
        covered_stale=covered_stale,
    )
