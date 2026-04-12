import json
import secrets
import math
from enum import StrEnum
from typing import List, cast, Optional, Any
from environment import get_env_vars
import shared.utils.id_utils
from shared.utils.statuses import JobStatus, PullRequestStatus, ReviewIssueStatus, TERMINAL_JOB_STATUSES
from utils import hash_utils
from utils.github_utils import pull_request_url_to_number
from schemas.requests import ServerDetail

from psycopg_pool import AsyncConnectionPool
from psycopg import sql

from schemas.common import PeopleJobHistory
from shared.schemas import Person

import logging
logger = logging.getLogger(__name__)


class PeopleStatus(StrEnum):
    CURRENT = "current"
    PAST = "past"


_pool: AsyncConnectionPool | None = None


def _on_reconnect_failed(pool: AsyncConnectionPool) -> None:
    logger.error("Database connection pool failed to reconnect — pool may be exhausted")


async def get_pool() -> AsyncConnectionPool:
    env = get_env_vars()

    global _pool
    if _pool is None:
        db_url = env["CIVICPATCH_API_DB_URL"]
        if not db_url:
            raise RuntimeError("CIVICPATCH_API_DB_URL is not set")
        _pool = AsyncConnectionPool(
            db_url,
            open=False,
            min_size=int(env.get("DB_POOL_MIN_SIZE", 4)),
            max_size=int(env.get("DB_POOL_MAX_SIZE", 20)),
            reconnect_failed=_on_reconnect_failed,
        )
        await _pool.open()
        logger.info("Database pool opened")
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def to_iso(dt):
    if dt:
        return dt.isoformat()
    return None

async def create_update_user(provider, provider_user_id, email, teams: List[str], display_name: str | None = None):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # Upsert user
        await cur.execute(
            """
            INSERT INTO users (provider, provider_user_id, email, display_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (provider, provider_user_id)
            DO UPDATE SET email = EXCLUDED.email, display_name = EXCLUDED.display_name
            """,
            (provider, provider_user_id, email, display_name),
        )
        # Remove existing teams for user
        await cur.execute(
            """
            DELETE FROM user_roles
            WHERE provider = %s AND provider_user_id = %s
            """,
            (provider, provider_user_id),
        )
        # Insert new teams for user (always present)
        await cur.executemany(
            """
            INSERT INTO user_roles (provider, provider_user_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, provider_user_id, role)
            DO NOTHING
            """,
            [(provider, provider_user_id, team) for team in teams],
        )


async def create_api_key(provider, provider_user_id):
    pool = await get_pool()
    env = get_env_vars()

    # Hash the API key before storing
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hash_utils.hash_string(api_key, cast(str, env["DATABASE_HASH_KEY"]))
    api_key_suffix = api_key[-4:]

    async with pool.connection() as conn:
        await conn.execute(
            """
        INSERT INTO api_keys (provider, provider_user_id, api_key_hash, api_key_suffix)
        VALUES (%s, %s, %s, %s)
    """,
            (provider, provider_user_id, api_key_hash, api_key_suffix),
        )
        return api_key


async def revoke_api_key(api_key_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
        UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """,
            (api_key_id,),
        )

async def delete_api_key(api_key_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM api_keys WHERE id = %s",
            (api_key_id,),
        )

async def get_api_keys_for_user(provider, provider_user_id):
    pool = await get_pool()
    data = []
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
        SELECT id, api_key_suffix, created_at, revoked_at FROM api_keys
        WHERE provider_user_id = %s AND provider = %s
    """,
            (provider_user_id, provider),
        )
        rows = await cur.fetchall()

        for row in rows:
            data.append(
                {
                    "id": row[0],
                    "suffix": row[1],
                    "created_at": row[2],
                    "revoked_at": row[3],
                }
            )
    return data

async def get_user(provider, provider_user_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                u.id,
                u.email,
                u.server_url,
                u.created_at,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles,
                u.display_name
            FROM users u
            LEFT JOIN user_roles r
                ON u.provider = r.provider AND u.provider_user_id = r.provider_user_id
            WHERE u.provider_user_id = %s AND u.provider = %s
            GROUP BY u.id, u.email, u.server_url, u.created_at, u.display_name
            """,
            (provider_user_id, provider),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "email": row[1],
            "server_url": row[2],
            "created_at": row[3],
            "teams": row[4],
            "display_name": row[5],
        }
async def get_user_by_api_key_id(api_key_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT u.provider,
                   u.provider_user_id
            FROM users u
            JOIN api_keys k ON u.provider = k.provider AND u.provider_user_id = k.provider_user_id
            LEFT JOIN user_roles r ON u.provider = r.provider AND u.provider_user_id = r.provider_user_id
            WHERE k.id = %s AND k.revoked_at IS NULL
            GROUP BY u.provider, u.provider_user_id, u.email, u.server_url, u.created_at
            """,
            (api_key_id,),
        )
        row = await result.fetchone()
        if not row:
            return None
        
        return {
            "provider": row[0],
            "provider_user_id": row[1]
        }
    
    
async def get_user_by_api_key(api_key):
    pool = await get_pool()
    env = get_env_vars()
    candidate_api_key_hash = hash_utils.hash_string(api_key, cast(str, env["DATABASE_HASH_KEY"]))
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                u.id,
                u.provider,
                u.provider_user_id,
                u.email,
                u.server_url,
                u.created_at,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles
            FROM users u
            JOIN api_keys k ON u.provider = k.provider AND u.provider_user_id = k.provider_user_id
            LEFT JOIN user_roles r ON u.provider = r.provider AND u.provider_user_id = r.provider_user_id
            WHERE k.api_key_hash = %s AND k.revoked_at IS NULL
            GROUP BY u.id, u.provider, u.provider_user_id, u.email, u.server_url, u.created_at
            """,
            (candidate_api_key_hash,),
        )
        row = await cur.fetchone()
        if not row:
            return None

        return {
            "id": str(row[0]),
            "provider": row[1],
            "provider_user_id": row[2],
            "email": row[3],
            "server_url": row[4],
            "created_at": row[5],
            "teams": row[6],
        }

async def get_user_details(provider, provider_user_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
        SELECT server_url, email FROM users
        WHERE provider_user_id = %s AND provider = %s
    """,
            (provider_user_id, provider),
        )
        row = await cur.fetchone()
    if row:
        return {
            "server_url": row[0],
            "user_email": row[1],
        }
    return None

    
async def get_server_detail_by_active_api_key(api_key) -> Optional[ServerDetail]:
    pool = await get_pool()
    env = get_env_vars()
    candidate_api_key_hash = hash_utils.hash_string(api_key, cast(str, env["DATABASE_HASH_KEY"]))
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
        SELECT u.email, u.server_url
        FROM users u
        JOIN api_keys k ON u.provider = k.provider AND u.provider_user_id = k.provider_user_id
        WHERE k.api_key_hash = %s AND k.revoked_at IS NULL
    """,
            (candidate_api_key_hash,),
        )
        row = await cur.fetchone()
    if row:
        return ServerDetail(
            user_email=row[0],
            server_url=row[1],
        )
    return None


async def update_user_detail(server_url, user_provider, user_provider_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE users
            SET server_url = %s
            WHERE provider = %s
            AND provider_user_id = %s
            """,
            (server_url, user_provider, user_provider_id),
        )


async def filter_existing_person_ids(ids: list[str]) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM people WHERE id = ANY(%s)",
            (ids,),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def get_jurisdiction_people(jurisdiction_ocdid: str) -> List[Person]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s
            """,
            (jurisdiction_ocdid,),
        )
        rows = await cur.fetchall()
        people = [Person(**row[0]) for row in rows]
    return people


async def get_all_people_for_jurisdiction(
    jurisdiction_ocdid: str, limit: int, offset: int
) -> tuple[int, list[dict]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) OVER(), id::text, data, status
            FROM people
            WHERE jurisdiction_ocdid = %s
            ORDER BY
                CASE WHEN status = 'current' THEN 0 ELSE 1 END,
                (data->>'updated_at') DESC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (jurisdiction_ocdid, limit, offset),
        )
        rows = await cur.fetchall()
    if not rows:
        return 0, []
    total = rows[0][0]
    return total, [{**row[2], "_id": row[1], "status": row[3]} for row in rows]


async def delete_person(person_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM people WHERE id = %s",
            (person_id,),
        )


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
    """
    Fetch a jurisdiction's data. If with_geom is True, attempt to join the geo table
    (on jurisdictions.data->>'geoid' = geo.geoid) and return the centroid (center)
    and the raw geo JSON (if available).

    Returns:
      - when with_geom=False: the jurisdiction data JSON (or None)
      - when with_geom=True: {"data": <json>, "center": {"lat":..,"lng":..} | None, "geojson": <geojson> | None} or None
    """
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
                center = {"lat": float(lat), "lng": float(lon)} if lon is not None and lat is not None else None
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
                return { "data": row[0] }
    except Exception as e:
        print(f"Error in get_jurisdiction: {e}")
        return None



async def get_jurisdiction_geom(jurisdiction_ocdid: str):
    """Return the GeoJSON geometry for the given jurisdiction_ocdid by resolving the jurisdiction's geoid
    and returning the corresponding geo.geom as GeoJSON (parsed JSON).
    """
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
    """Find people for jurisdictions whose geo polygons intersect the given point.

    This uses a single JOIN query with LATERAL jsonb_array_elements to return one person
    JSON per row, which we then parse into Person objects.
    """
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            # Use ST_Intersects as the single spatial predicate
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
            for (jurisdiction_ocdid, _jurisdiction_data, person_json) in rows:
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
    """
    Return multiple GeoJSON geometries from geo for polygons near the given point.
    At low zoom (zoomed out), geometries are simplified and exaggerated (buffered).
    """
    pool = await get_pool()
    if zoom is None:
        buffer_m = 1000.0
        simplify_tolerance = 0.01
        result_limit = 100
        exaggerate_buffer = 0
    else:
        meters_per_pixel = 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)
        buffer_m = max(50.0, meters_per_pixel * 512.0)
        if zoom < 7:
            simplify_tolerance = 0.05
            result_limit = 20
            exaggerate_buffer = 5000  # exaggerate by 5km at low zoom
        elif zoom < 10:
            simplify_tolerance = 0.01
            result_limit = 50
            exaggerate_buffer = 1000  # exaggerate by 1km at mid zoom
        else:
            simplify_tolerance = 0.001
            result_limit = 100
            exaggerate_buffer = 0  # no exaggeration at high zoom

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
            # Use ST_Buffer if exaggerate_buffer > 0, else just simplify
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
                    exaggerate_buffer, simplify_tolerance
                    if exaggerate_buffer > 0 else simplify_tolerance,
                    long, lat,
                    min_lon, min_lat, max_lon, max_lat,
                    long, lat,
                    buffer_m,
                    result_limit,
                ) if exaggerate_buffer > 0 else (
                    simplify_tolerance,
                    long, lat,
                    min_lon, min_lat, max_lon, max_lat,
                    long, lat,
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
        return {"results": [], "buffer_m": buffer_m if 'buffer_m' in locals() else None}

async def search_jurisdictions(state: str, search_string = "", limit: int = 100, skip: int = 0):
    """
    Retrieves a paginated list of jurisdictions and the total count for a given state.

    Returns: A tuple (total_count, list_of_jurisdictions)
    """
    if limit <= 0:
        limit = 100  # Set a default reasonable limit if 0 is passed

    where_clauses: list[sql.Composable] = [sql.SQL("state = %s"), sql.SQL("status = 'current'")]
    params = [state.lower()]

    if search_string:
        where_clauses.append(sql.SQL("LOWER(data->>'name') LIKE %s"))
        params.append(f"%{search_string.lower()}%")

    where_condition = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(where_clauses))

    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                sql.SQL("SELECT COUNT(*) FROM jurisdictions {};").format(where_condition),
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

            # Fetch all matching records
            results = await cur.fetchall()

            # Process the results
            jurisdictions = []
            for row in results:
                jurisdictions.append({
                    "jurisdiction_ocdid": row[0],
                    "jurisdiction_path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(row[0]),
                    **row[1],
                })

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

# Jobs

async def list_jobs():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT request_id, status, progress, created_at, updated_at FROM jobs
            ORDER BY created_at DESC;
            """,
        )
        rows = await cur.fetchall()
        jobs = []
        for row in rows:
            jobs.append(
                {
                    "request_id": row[0],
                    "status": row[1],
                    "progress": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                }
            )
    return jobs


async def get_job(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.status, j.progress, r.arguments_json, r.data_json,
                   j.created_at, j.updated_at, pr.url
            FROM jobs j
            LEFT JOIN requests r ON r.id = j.request_id
            LEFT JOIN pull_requests pr ON pr.request_id = r.id
            WHERE j.request_id = %s;
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if row:
            return {
                "request_id": request_id,
                "status": row[0],
                "progress": row[1],
                "arguments_json": row[2],
                "data_json": row[3],
                "created_at": to_iso(row[4]),
                "updated_at": to_iso(row[5]),
                "pull_request_url": row[6],
            }
        return None

async def set_job_github_run_id(request_id: str, github_run_id: int) -> bool:
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            "UPDATE jobs SET github_run_id = %s WHERE request_id = %s",
            (github_run_id, request_id),
        )
        return result.rowcount > 0


async def get_active_job_jurisdiction_ocdids() -> set[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT r.jurisdiction_ocdid
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            WHERE j.status != ALL(%s)
            AND r.jurisdiction_ocdid IS NOT NULL
            """,
            (list(TERMINAL_JOB_STATUSES),),
        )
        rows = await cur.fetchall()
        return {row[0] for row in rows}


async def get_active_jobs(state_code: Optional[str] = None, page: int = 1, per_page: int = 25) -> tuple[list[dict], int]:
    pool = await get_pool()
    offset = (page - 1) * per_page
    async with pool.connection() as conn, conn.cursor() as cur:
        query = """
            SELECT j.request_id, j.status, j.progress, j.created_at, j.updated_at,
                   r.jurisdiction_ocdid, jur.state, jur.data->>'name',
                   COUNT(*) OVER() AS total_count
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE j.status != ALL(%s)
            AND r.jurisdiction_ocdid IS NOT NULL
            AND r.request_type = 'people'
        """
        params: list = [list(TERMINAL_JOB_STATUSES)]
        if state_code:
            query += " AND jur.state = %s"
            params.append(state_code.lower())
        query += " ORDER BY j.updated_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        await cur.execute(query, params)
        rows = await cur.fetchall()
        total = rows[0][8] if rows else 0
        return [
            {
                "request_id": row[0],
                "status": row[1],
                "progress": row[2],
                "created_at": to_iso(row[3]),
                "updated_at": to_iso(row[4]),
                "jurisdiction_ocdid": row[5],
                "state": row[6],
                "jurisdiction_name": row[7],
            }
            for row in rows
        ], total


async def get_job_github_run_id(request_id: str) -> int | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT github_run_id FROM jobs WHERE request_id = %s",
            (request_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def get_job_status(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT status, progress FROM jobs
            WHERE request_id = %s;
            """,
            (request_id,),
        )
        row = await cur.fetchone()
        if row:
            return {"request_id": request_id, "status": row[0], "progress": row[1]}
        return None

async def update_job_status(request_id: str, status: str | None = None, progress: Optional[int] = None):
    pool = await get_pool()
    set_clauses = []
    params = []

    if progress is not None:
        set_clauses.append("progress = %s")
        params.append(progress)
    if status is not None:
        set_clauses.append("status = %s")
        params.append(status)

    # Always update updated_at
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    if not set_clauses:
        # Nothing to update
        return

    params.append(request_id)
    set_clause_str = ", ".join(set_clauses)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(f"""
            UPDATE jobs
            SET {set_clause_str}
            WHERE request_id = %s;
            """),
            params,
        )

async def update_job_data(request_id: str, data_json: Any):
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            UPDATE requests r
            SET data_json = %s,
                updated_at = CURRENT_TIMESTAMP
            FROM jobs j
            WHERE r.id = j.request_id AND j.request_id = %s;
            """,
            (
                json.dumps(data_json),
                request_id,
            ),
        )
        if result.rowcount == 0:
            return False
        return True

async def update_job_pull_request_url(request_id: str, pull_request_url: str | None = None):
    pool = await get_pool()
    pr_number = 0
    if pull_request_url:
        num = pull_request_url_to_number(pull_request_url)
        pr_number = int(num) if num else 0

    async with pool.connection() as conn:
        result = await conn.execute(
            """
            INSERT INTO pull_requests (request_id, url, status, pr_number, created_at, updated_at)
            VALUES (%s, %s, 'open', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (request_id) DO UPDATE
                SET url = EXCLUDED.url,
                    status = CASE
                        WHEN pull_requests.status IN ('merged', 'closed') THEN pull_requests.status
                        ELSE 'open'
                    END,
                    updated_at = CURRENT_TIMESTAMP
            """,
            (request_id, pull_request_url, pr_number),
        )
        return result.rowcount > 0

async def get_api_usage_for_user(provider: str, provider_user_id: str):
    pool = await get_pool()
    # Queries api_usage_limits to get daily_limit
    # Joins with jobs table to count jobs created in the last 24 hours 
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                ul.daily_limit,
                COUNT(r.id) AS usage_count
            FROM api_usage_limits ul
            LEFT JOIN users u ON u.provider = ul.provider AND u.provider_user_id = ul.provider_user_id
            LEFT JOIN requests r ON r.requested_by_user_id = u.id
                AND r.created_at >= NOW() - INTERVAL '24 hours'
            WHERE ul.provider = %s AND ul.provider_user_id = %s
            GROUP BY ul.daily_limit;
            """,
            (provider, provider_user_id),
        )
        row = await cur.fetchone()
        if row:
            return {
                "daily_limit": row[0],
                "usage_count": row[1],
            }
        else:
            return {
                "daily_limit": 0,
                "usage_count": 0,
            }
        
async def set_daily_limit_for_user(provider: str, provider_user_id: str, daily_limit: int = 100):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO api_usage_limits (provider, provider_user_id, daily_limit)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, provider_user_id) 
            DO UPDATE SET daily_limit = EXCLUDED.daily_limit;
            """,
            (provider, provider_user_id, daily_limit),
        )
async def get_jurisdiction_states():
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

### Jurisdiction History ###
async def get_jurisdiction_history(jurisdiction_ocdid) -> List[PeopleJobHistory]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.request_id, j.created_at, j.updated_at, j.status, j.progress, pr.url
            FROM jobs j
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
            branch_name = shared.utils.id_utils.make_git_branch(jurisdiction_ocdid, row[0])
            history.append(
                {
                    "request_id": row[0],
                    "created_at": to_iso(row[1]),
                    "updated_at": to_iso(row[2]),
                    "status": row[3],
                    "progress": row[4],
                    "pull_request_url": row[5],
                    "jurisdiction_ocdid": jurisdiction_ocdid,
                    "branch_name": branch_name
                }
            )
    return history

import datetime

async def update_jurisdiction(jurisdiction_ocdid, state, data: dict):
    """
    Update jurisdiction record(s) in the database for a single jurisdiction_ocdid.
    """
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
            (jurisdiction_ocdid, state, data_json, updated_at)
        )

# Probably could be optimized more, but maybe not worth it
# for the scale of our data...
async def bulk_update_people(people_records: list):
    if not people_records:
        return

    # Group incoming records by jurisdiction_ocdid
    jurisdictions: dict = {}
    for record in people_records:
        person_id, jurisdiction_ocdid = record[0], record[1]
        if jurisdiction_ocdid not in jurisdictions:
            jurisdictions[jurisdiction_ocdid] = []
        jurisdictions[jurisdiction_ocdid].append(person_id)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # Upsert all incoming people with status "current"
        insert_query = """
            INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
            VALUES (%s, %s, %s, %s, 'current')
            ON CONFLICT (id)
            DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at,
                status = 'current'
        """
        await cur.executemany(insert_query, people_records)

        # For each jurisdiction, mark people not in the incoming set as "past"
        for jurisdiction_ocdid, incoming_ids in jurisdictions.items():
            await cur.execute(
                """
                UPDATE people
                SET status = 'past'
                WHERE jurisdiction_ocdid = %s
                  AND id != ALL(%s)
                """,
                (jurisdiction_ocdid, incoming_ids)
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
        INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (jurisdiction_ocdid)
        DO UPDATE SET
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

async def get_people_for_jurisdiction(jurisdiction_ocdid: str, status: str | None = None) -> List[Person]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if status is not None:
            await cur.execute(
                """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s AND status = %s
                """,
                (jurisdiction_ocdid, status),
            )
        else:
            await cur.execute(
                """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s
                """,
                (jurisdiction_ocdid,),
            )
        rows = await cur.fetchall()
        people = [Person(**row[0]) for row in rows]
    return people

async def get_user_id_by_provider(provider: str, provider_user_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM users WHERE provider = %s AND provider_user_id = %s",
            (provider, provider_user_id),
        )
        row = await cur.fetchone()
    return str(row[0]) if row else None


async def update_job_pull_request_status(
    request_id: str,
    pull_request_status: str,
    pull_request_merged_at=None,
    pull_request_url: Optional[str] = None,
    resolved_by_user_id: Optional[str] = None,
) -> bool:
    pool = await get_pool()
    pr_number = 0
    if pull_request_url:
        num = pull_request_url_to_number(pull_request_url)
        pr_number = int(num) if num else 0

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1 FROM requests WHERE id = %s", (request_id,))
        if not await cur.fetchone():
            return False
        await cur.execute(
            """
            INSERT INTO pull_requests (request_id, url, status, merged_at, pr_number, resolved_by_user_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (request_id) DO UPDATE
                SET status = EXCLUDED.status,
                    merged_at = EXCLUDED.merged_at,
                    url = COALESCE(EXCLUDED.url, pull_requests.url),
                    resolved_by_user_id = EXCLUDED.resolved_by_user_id,
                    updated_at = CURRENT_TIMESTAMP
            """,
            (request_id, pull_request_url, pull_request_status, pull_request_merged_at, pr_number, resolved_by_user_id),
        )
        return True





async def count_jobs_with_errors(state_code: Optional[str] = None) -> int:
    conditions: list[sql.Composable] = [sql.SQL("j.status = 'ERROR'")]
    params: list = []

    if state_code:
        conditions.append(sql.SQL("r.jurisdiction_ocdid LIKE %s"))
        params.append(f"%state:{state_code}%")

    where = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(conditions))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT COUNT(*)
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            {}
            """).format(where),
            params,
        )
        row = await cur.fetchone()

    return row[0] if row is not None else 0


async def get_jobs_with_errors(state_code: Optional[str] = None) -> List[dict]:
    conditions: list[sql.Composable] = [sql.SQL("j.status = 'ERROR'")]
    params: list = []

    if state_code:
        conditions.append(sql.SQL("r.jurisdiction_ocdid LIKE %s"))
        params.append(f"%state:{state_code}%")

    where = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(conditions))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT j.request_id,
                   r.jurisdiction_ocdid AS jurisdiction_ocdid,
                   jur.data->>'name' AS jurisdiction_name,
                   j.status,
                   j.created_at, j.updated_at
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            LEFT JOIN jurisdictions jur ON jur.jurisdiction_ocdid = r.jurisdiction_ocdid
            {}
            ORDER BY j.created_at DESC
            """).format(where),
            params,
        )
        rows = await cur.fetchall()

    return [
        {
            "request_id": r[0],
            "jurisdiction_ocdid": r[1],
            "jurisdiction_name": r[2],
            "status": r[3],
            "created_at": to_iso(r[4]),
            "updated_at": to_iso(r[5]),
        }
        for r in rows
    ]


async def get_job_data_json(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.data_json
            FROM jobs j
            LEFT JOIN requests r ON r.id = j.request_id
            WHERE j.request_id = %s LIMIT 1
            """,
            (request_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def get_job_result(request_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.data_json, r.review_json FROM requests r
            JOIN jobs j ON j.request_id = r.id
            WHERE j.request_id = %s LIMIT 1
            """,
            (request_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {"data": row[0], "review_json": row[1]}


async def update_job_pull_request_review_state(request_id: str, review_state: str | None):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pull_requests
            SET review_state = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE request_id = %s;
            """,
            (review_state, request_id),
        )


async def update_job_review_json(request_id: str, review_json: dict):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE requests r
            SET review_json = %s,
                updated_at = CURRENT_TIMESTAMP
            FROM jobs j
            WHERE r.id = j.request_id AND j.request_id = %s;
            """,
            (json.dumps(review_json), request_id),
        )


async def get_open_pr_request_ids() -> dict[str, str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.request_id, pr.url
            FROM jobs j
            JOIN requests r ON r.id = j.request_id
            JOIN pull_requests pr ON pr.request_id = r.id
            WHERE pr.status = 'open'
            """
        )
        rows = await cur.fetchall()
    return {r[0]: r[1] for r in rows}


async def bulk_close_stale_prs(request_ids: List[str]):
    if not request_ids:
        return
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE pull_requests pr
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            FROM jobs j
            WHERE pr.request_id = j.request_id AND j.request_id = ANY(%s)
            """,
            (request_ids,),
        )


async def get_requests_for_export(
    state: str,
    from_date: str | None,
    to_date: str | None,
) -> list[dict]:
    state_prefix = f"ocd-jurisdiction/country:us/state:{state.lower()}%"
    params: list = [state_prefix]
    date_clauses = ""
    if from_date:
        params.append(from_date)
        date_clauses += f" AND r.created_at >= %s"
    if to_date:
        params.append(to_date)
        date_clauses += f" AND r.created_at <= %s"

    pool = await get_pool()
    rows = []
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL(f"""
            SELECT r.id, r.jurisdiction_ocdid, r.created_at, r.data_json, r.review_json
            FROM requests r
            JOIN pull_requests pr ON pr.request_id = r.id
            WHERE r.jurisdiction_ocdid LIKE %s
              AND pr.status = 'open'
              {date_clauses}
            ORDER BY r.created_at DESC
            """),
            params,
        )
        while True:
            batch = await cur.fetchmany(200)
            if not batch:
                break
            rows.extend(batch)
    return [
        {
            "request_id": str(r[0]),
            "jurisdiction_ocdid": r[1],
            "created_at": r[2].isoformat() if r[2] else None,
            "data_json": r[3] or [],
            "review_json": r[4] or {},
        }
        for r in rows
    ]


async def get_people_by_state(state: str) -> list[dict]:
    state_prefix = f"ocd-jurisdiction/country:us/state:{state.lower()}%"
    pool = await get_pool()
    rows = []
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, data
            FROM people
            WHERE jurisdiction_ocdid LIKE %s
              AND status = 'current'
            ORDER BY jurisdiction_ocdid
            """,
            (state_prefix,),
        )
        while True:
            batch = await cur.fetchmany(200)
            if not batch:
                break
            rows.extend(batch)
    return [{"jurisdiction_ocdid": r[0], **r[1]} for r in rows]


async def deactivate_jurisdictions_by_ocdids(ocdids: List[str]):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE jurisdictions SET status = 'inactive' WHERE jurisdiction_ocdid = ANY(%s)",
            (ocdids,)
        )


async def get_unrecognized_roles_grouped() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT issue_key AS role,
                   request_ids,
                   data->'person_names' AS person_names,
                   array_length(request_ids, 1) AS occurrence_count
            FROM review_issues
            WHERE issue_type = 'unrecognized_role'
              AND status = 'pending'
            ORDER BY array_length(request_ids, 1) DESC
            """
        )
        rows = await cur.fetchall()
    return [
        {
            "role": r[0],
            "request_ids": r[1],
            "person_names": r[2] or [],
            "occurrence_count": r[3],
        }
        for r in rows
    ]


async def resolve_unrecognized_role_group(request_ids: list[str]) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE review_session_entries
            SET status = 'resolved', resolved_at = NOW()
            WHERE request_ids && %s::text[]
              AND status != 'resolved'
            """,
            (request_ids,),
        )


async def resolve_review_issue(issue_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_issues SET status = %s, resolved_at = NOW() WHERE id = %s",
            (ReviewIssueStatus.RESOLVED, issue_id),
        )


async def open_review_issue_pull_request(issue_id: str, pull_request_url: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_issues SET status = %s, pull_request_url = %s WHERE id = %s",
            (ReviewIssueStatus.PR_OPENED, pull_request_url, issue_id),
        )


async def upsert_review_issue(request_id: str, issue_type: str, issues: list[dict]) -> None:
    if not issues:
        return
    rows = []
    for issue in issues:
        if issue_type == "unrecognized_role":
            issue_key = issue["role"]
            data = json.dumps({"person_names": [issue.get("person_name", "")]})
        elif issue_type == "dead_url":
            issue_key = f"{issue['url']}::{request_id}"
            data = json.dumps(issue)
        else:
            issue_key = request_id
            data = json.dumps(issue)
        rows.append((issue_type, issue_key, [request_id], data, ReviewIssueStatus.PENDING))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO review_issues (issue_type, issue_key, request_ids, data, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (issue_type, issue_key) DO UPDATE SET
              request_ids = (
                SELECT array_agg(DISTINCT r)
                FROM unnest(review_issues.request_ids || EXCLUDED.request_ids) r
              ),
              data = CASE
                WHEN review_issues.issue_type = 'unrecognized_role' THEN
                  jsonb_set(
                    review_issues.data,
                    '{person_names}',
                    (SELECT jsonb_agg(DISTINCT v)
                     FROM jsonb_array_elements_text(
                       COALESCE(review_issues.data->'person_names', '[]'::jsonb) ||
                       COALESCE(EXCLUDED.data->'person_names', '[]'::jsonb)
                     ) v)
                  )
                ELSE review_issues.data
              END,
              status = %s,
              resolved_at = NULL
            """,
            rows,
        )


def _build_jurisdictions(ocdids: list[str] | None) -> list[dict]:
    result = []
    for ocdid in (ocdids or []):
        try:
            folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(ocdid)
            parts = folder.split("/")
            result.append({
                "jurisdiction_ocdid": ocdid,
                "folder": folder,
                "state": parts[0] if parts else "",
                "locality": parts[2] if len(parts) > 2 else "",
            })
        except Exception:
            pass
    return result


async def get_review_issues_page(
    issue_types: list[str],
    page: int,
    per_page: int,
    sort_desc: bool = True,
) -> tuple[list[dict], int]:
    conditions: list[sql.Composable] = [
        sql.SQL("ri.status IN ({})").format(
            sql.SQL(", ").join(sql.Placeholder() for _ in range(2))
        )
    ]
    params: list[Any] = [ReviewIssueStatus.PENDING, ReviewIssueStatus.PR_OPENED]
    if issue_types:
        conditions.append(
            sql.SQL("ri.issue_type IN ({})").format(
                sql.SQL(", ").join(sql.Placeholder() for _ in range(len(issue_types)))
            )
        )
        params.extend(issue_types)
    where_clause = sql.SQL("WHERE ") + sql.SQL(" AND ").join(conditions)
    order_clause = sql.SQL("DESC") if sort_desc else sql.SQL("ASC")
    offset = (page - 1) * per_page
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            WITH issue_jurisdictions AS (
                SELECT ri.id AS issue_id,
                       array_agg(DISTINCT r.jurisdiction_ocdid)
                           FILTER (WHERE r.jurisdiction_ocdid IS NOT NULL) AS ocdids
                FROM review_issues ri
                LEFT JOIN requests r ON r.id::text = ANY(ri.request_ids)
                GROUP BY ri.id
            )
            SELECT ri.id::text, ri.issue_type, ri.issue_key, ri.request_ids,
                   ri.data, ri.status, ri.resolved_at, ri.created_at,
                   COALESCE(ij.ocdids, ARRAY[]::text[]) AS raw_jurisdiction_ocdids,
                   COUNT(*) OVER() AS total_count,
                   ri.pull_request_url
            FROM review_issues ri
            LEFT JOIN issue_jurisdictions ij ON ij.issue_id = ri.id
            {where}
            ORDER BY ri.created_at {order}
            LIMIT %s OFFSET %s
            """).format(where=where_clause, order=order_clause),
            params + [per_page, offset],
        )
        rows = await cur.fetchall()
    total = rows[0][9] if rows else 0
    result = []
    for r in rows:
        jurisdictions = _build_jurisdictions(r[8])
        result.append({
            "id": r[0],
            "issue_type": r[1],
            "issue_key": r[2],
            "request_ids": r[3],
            "data": r[4],
            "status": r[5],
            "resolved_at": r[6].isoformat() if r[6] else None,
            "created_at": r[7].isoformat() if r[7] else None,
            "pull_request_url": r[10],
            "states": sorted({j["state"] for j in jurisdictions if j["state"]}),
            "jurisdictions": jurisdictions,
        })
    return result, total


async def get_review_issue_by_id(issue_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, issue_type, issue_key, request_ids, data, status, resolved_at, created_at
            FROM review_issues WHERE id = %s
            """,
            (issue_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "issue_type": row[1],
        "issue_key": row[2],
        "request_ids": row[3],
        "data": row[4],
        "status": row[5],
        "resolved_at": row[6].isoformat() if row[6] else None,
        "created_at": row[7].isoformat() if row[7] else None,
    }


async def get_request_jurisdiction(request_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid FROM requests WHERE id::text = %s",
            (request_id,),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def get_issue_request_details(request_ids: list[str]) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.id::text, r.jurisdiction_ocdid, r.arguments_json,
                   COALESCE(r.data_json, '[]'::jsonb) AS data_json,
                   COALESCE(j.data->>'name', r.jurisdiction_ocdid) AS jurisdiction_name
            FROM requests r
            LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = r.jurisdiction_ocdid
            WHERE r.id::text = ANY(%s)
            ORDER BY r.created_at
            """,
            (request_ids,),
        )
        rows = await cur.fetchall()
    return [
        {
            "request_id": r[0],
            "jurisdiction_ocdid": r[1],
            "arguments_json": r[2] or {},
            "data_json": r[3] or [],
            "jurisdiction_name": r[4],
        }
        for r in rows
    ]


async def get_notes_for_jurisdiction(jurisdiction_ocdid: str, limit: int, offset: int):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) FROM notes WHERE jurisdiction_ocdid = %s
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
        total = row[0] if row is not None else 0

        await cur.execute(
            """
            SELECT
                n.id::text,
                n.jurisdiction_ocdid,
                n.body,
                n.user_id::text,
                n.created_at,
                CASE WHEN u.provider = 'github'
                    THEN 'https://avatars.githubusercontent.com/u/' || u.provider_user_id
                    ELSE NULL
                END AS avatar_url,
                u.display_name,
                CASE WHEN u.provider = 'github'
                    THEN 'https://github.com/' || u.display_name
                    ELSE NULL
                END AS profile_url
            FROM notes n
            LEFT JOIN users u ON u.id = n.user_id
            WHERE n.jurisdiction_ocdid = %s
            ORDER BY n.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (jurisdiction_ocdid, limit, offset),
        )
        rows = await cur.fetchall()

    notes = [
        {
            "id": r[0],
            "jurisdiction_ocdid": r[1],
            "body": r[2],
            "user_id": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
            "avatar_url": r[5],
            "display_name": r[6],
            "profile_url": r[7],
        }
        for r in rows
    ]
    return total, notes


async def create_note(jurisdiction_ocdid: str, body: str, user_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO notes (jurisdiction_ocdid, body, user_id)
            VALUES (%s, %s, %s)
            RETURNING id::text, jurisdiction_ocdid, body, user_id::text, created_at
            """,
            (jurisdiction_ocdid, body, user_id),
        )
        r = await cur.fetchone()
    if r is None:
        raise RuntimeError("INSERT RETURNING returned no row")
    return {
        "id": r[0],
        "jurisdiction_ocdid": r[1],
        "body": r[2],
        "user_id": r[3],
        "created_at": r[4].isoformat() if r[4] else None,
    }


async def get_summary_counts(include_issues: bool) -> dict:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM pull_requests WHERE status = 'open') AS open_prs,
                (SELECT COUNT(*) FROM jobs WHERE status = 'ERROR') AS pipeline_errors,
                (SELECT COUNT(*) FROM review_issues WHERE status = 'pending') AS issues_total,
                (SELECT COUNT(*) FROM (
                    SELECT r.jurisdiction_ocdid
                    FROM jobs j
                    JOIN requests r ON r.id = j.request_id
                    JOIN pull_requests pr ON pr.request_id = r.id
                    WHERE pr.status = 'open'
                    GROUP BY r.jurisdiction_ocdid
                    HAVING COUNT(*) > 1
                ) sub) AS duplicate_jurisdictions
            """
        )
        row = await cur.fetchone()
    if row is None:
        raise RuntimeError("Summary counts query returned no row")
    result: dict = {"open_prs": row[0]}
    if include_issues:
        result["pipeline_errors"] = row[1]
        result["issues_total"] = row[2]
        result["duplicate_jurisdictions"] = row[3]
    return result