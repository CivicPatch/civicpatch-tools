import datetime
import json
import math
from typing import List

import shared.utils.id_utils
from database.database import get_pool, to_iso
from psycopg import sql
from schemas.common import PeoplePipelineRunHistory
from shared.schemas import Person


def jurisdiction_rows(
    entries: list[dict[str, str]], state: str, level: str, updated_at
):
    return [(entry["id"], state, level, json.dumps(entry), updated_at) for entry in entries]


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
                        ST_Y(ST_Centroid(g.geom)) AS lat
                    FROM jurisdictions j
                    LEFT JOIN geo g ON j.data->>'geoid' = g.geoid
                    WHERE j.jurisdiction_ocdid = %s AND j.status = 'current'
                    LIMIT 1;
                    """,
                    (jurisdiction_ocdid,),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                data, lon, lat = row[0], row[1], row[2]
                center = (
                    {"lat": float(lat), "lng": float(lon)}
                    if lon is not None and lat is not None
                    else None
                )
                return {"data": data, "geo_center": center}
            else:
                await cur.execute(
                    """
                    SELECT data FROM jurisdictions
                    WHERE jurisdiction_ocdid = %s AND status = 'current'
                    LIMIT 1;
                    """,
                    (jurisdiction_ocdid,),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                return {"data": row[0]}
    except Exception as e:
        print(f"Error in get_jurisdiction: {e}")
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
    except Exception as e:
        print(f"Error in get_jurisdiction_geom: {e}")
        return None


async def get_people_by_geo(lat: float, long: float):
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT j.jurisdiction_ocdid, j.data, p.data
                FROM geo g
                JOIN jurisdictions j ON j.data->>'geoid' = g.geoid
                JOIN people p ON p.jurisdiction_ocdid = j.jurisdiction_ocdid
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
    except Exception as e:
        print(f"Error in get_people_by_geo: {e}")
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
    except Exception as e:
        print(f"Error in get_geojson_by_latlong: {e}")
        return {"results": [], "buffer_m": buffer_m if "buffer_m" in locals() else None}


async def search_jurisdictions(
    state: str, search_string="", limit: int = 100, skip: int = 0
):
    if limit <= 0:
        limit = 100

    where_clauses: list[sql.Composable] = [
        sql.SQL("state = %s"),
        sql.SQL("status = 'current'"),
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

    except Exception as e:
        print(f"Database error in get_jurisdictions: {e}")
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


async def get_jurisdiction_history(
    jurisdiction_ocdid,
) -> List[PeoplePipelineRunHistory]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.request_id, j.created_at, j.updated_at, j.status, j.progress, pr.url, pr.status
            FROM pipeline_runs j
            JOIN requests r ON r.id = j.request_id
            LEFT JOIN pull_requests pr ON pr.request_id = r.id
            WHERE r.jurisdiction_ocdid = %s AND r.request_type = %s
            ORDER BY j.created_at DESC;
            """,
            (jurisdiction_ocdid, "people"),
        )
        rows = await cur.fetchall()
        history = []
        for row in rows:
            branch_name = shared.utils.id_utils.make_job_branch(
                jurisdiction_ocdid, row[0]
            )
            history.append(
                {
                    "request_id": row[0],
                    "created_at": to_iso(row[1]),
                    "updated_at": to_iso(row[2]),
                    "job_status": row[3],
                    "job_progress": row[4],
                    "pull_request_url": row[5],
                    "pull_request_status": row[6],
                    "jurisdiction_ocdid": jurisdiction_ocdid,
                    "branch_name": branch_name,
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


async def mark_jurisdictions_inactive(jurisdiction_ocdids: list):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            "UPDATE jurisdictions SET status = 'inactive' WHERE jurisdiction_ocdid = %s",
            [(ocdid,) for ocdid in jurisdiction_ocdids],
        )


async def bulk_update_jurisdictions(jurisdiction_records: list):
    query = """
        INSERT INTO jurisdictions (jurisdiction_ocdid, state, level, data, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (jurisdiction_ocdid)
        DO UPDATE SET
            level = EXCLUDED.level,
            data = EXCLUDED.data,
            updated_at = EXCLUDED.updated_at,
            status = 'current'
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(query, jurisdiction_records)


async def get_jurisdiction_updates() -> dict[str, dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.jurisdiction_ocdid, j.updated_at, COUNT(p.id) AS people_count
            FROM jurisdictions j
            LEFT JOIN people p ON p.jurisdiction_ocdid = j.jurisdiction_ocdid
            GROUP BY j.jurisdiction_ocdid, j.updated_at
            ORDER BY j.jurisdiction_ocdid;
            """
        )
        rows = await cur.fetchall()
        jurisdictions = {}
        for row in rows:
            jurisdictions[row[0]] = {
                "jurisdiction_ocdids": row[0],
                "updated_at": to_iso(row[1]),
                "people_count": row[2],
            }
    return jurisdictions


async def deactivate_jurisdictions_by_ocdids(ocdids: List[str]):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE jurisdictions SET status = 'inactive' WHERE jurisdiction_ocdid = ANY(%s)",
            (ocdids,),
        )
