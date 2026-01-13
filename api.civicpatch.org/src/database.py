import json
import hashlib
import hmac
import os
import secrets
import math
from typing import List, cast

from psycopg_pool import AsyncConnectionPool

from schemas import Person

CRUDDER_DB_URL = os.getenv("CRUDDER_DB_URL")
DATABASE_HASH_KEY = os.getenv("DATABASE_HASH_KEY")

pool = AsyncConnectionPool(CRUDDER_DB_URL, open=False)


def hash_string(string: str, hash_key: str) -> str:
    return hmac.new(hash_key.encode(), string.encode(), hashlib.sha512).hexdigest()


async def maybe_insert_user(provider, provider_user_id, email):
    async with pool.connection() as conn:
        # Try to insert the user; check if it was newly created
        result = await conn.execute(
            """
            INSERT INTO users (provider, provider_user_id, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, provider_user_id) DO NOTHING
            """,
            (provider, provider_user_id, email),
        )
        # If result.rowcount > 0, the user was newly inserted
        if result.rowcount > 0:
            # Insert 'unverified' role for new user
            await conn.execute(
                """
                INSERT INTO user_roles (provider, provider_user_id, role)
                VALUES (%s, %s, %s)
                """,
                (provider, provider_user_id, "unverified"),
            )
        else:
            # User already exists, just update email if needed
            await conn.execute(
                """
                UPDATE users SET email = %s
                WHERE provider = %s AND provider_user_id = %s
                """,
                (email, provider, provider_user_id),
            )


async def create_api_key(provider, provider_user_id):
    api_key = secrets.token_urlsafe(32)
    # Hash the API key before storing
    api_key_hash = hash_string(api_key, cast(str, DATABASE_HASH_KEY))
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
    async with pool.connection() as conn:
        await conn.execute(
            """
        UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """,
            (api_key_id,),
        )


async def get_api_keys_for_user(provider, provider_user_id):
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
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                u.email,
                u.server_url,
                u.created_at,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles
            FROM users u
            LEFT JOIN user_roles r
                ON u.provider = r.provider AND u.provider_user_id = r.provider_user_id
            WHERE u.provider_user_id = %s AND u.provider = %s
            GROUP BY u.email, u.server_url, u.created_at
            """,
            (provider_user_id, provider),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return {
            "email": row[0],
            "server_url": row[1],
            "created_at": row[2],
            "roles": row[3], 
        }

async def get_user_by_api_key(api_key):
    candidate_api_key_hash = hash_string(api_key, DATABASE_HASH_KEY)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
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
            GROUP BY u.provider, u.provider_user_id, u.email, u.server_url, u.created_at
            """,
            (candidate_api_key_hash,),
        )
        row = await cur.fetchone()
        if not row:
            return None

        return {
            "provider": row[0],
            "provider_user_id": row[1],
            "email": row[2],
            "server_url": row[3],
            "created_at": row[4],
            "roles": row[5],
        }

async def get_user_details(provider, provider_user_id):
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


async def user_is_approved(user_provider, provider_user_id) -> bool:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM users
                WHERE provider = %s
                  AND provider_user_id = %s
            ) AS is_user_approved;
            """,
            (user_provider, provider_user_id),
        )
        row = await cur.fetchone()
        return row[0] if row else False
    
async def get_server_detail_by_active_api_key(api_key):
    candidate_api_key_hash = hash_string(api_key, DATABASE_HASH_KEY)
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
        return {
            "user_email": row[0],
            "server_url": row[1],
        }
    return None


async def update_user_detail(server_url, user_provider, user_provider_id):
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


async def get_jurisdiction_people(jurisdiction_ocdid: str) -> List[Person]:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    if row:
        people_data = row[0]
    else:
        people_data = []
    people = [Person(**d_item) for d_item in people_data]
    return people


async def get_jurisdiction_states() -> List[str]:
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
                    WHERE j.jurisdiction_ocdid = %s
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
                    WHERE jurisdiction_ocdid = %s
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
        async with pool.connection() as conn, conn.cursor() as cur:
            # Use ST_Intersects as the single spatial predicate
            await cur.execute(
                """
                SELECT j.jurisdiction_ocdid, j.data, per.person
                FROM geo g
                JOIN jurisdictions j ON j.data->>'geoid' = g.geoid
                JOIN people p ON p.jurisdiction_ocdid = j.jurisdiction_ocdid
                CROSS JOIN LATERAL jsonb_array_elements(p.data) AS per(person)
                WHERE ST_Intersects(g.geom, ST_SetSRID(ST_Point(%s, %s), 4326))
                """,
                (long, lat),
            )
            rows = await cur.fetchall()

            if not rows:
                print(f"get_people_by_geo: no matching geo rows for point ({lat},{long})")
                return {"jurisdiction_ocdid": "", "people": []}

            # Since only one jurisdiction is expected, pick the first matched jurisdiction
            first_jurisdiction = rows[0][0]
            people_list = []
            for (jurisdiction_ocdid, _jurisdiction_data, person_json) in rows:
                try:
                    person_obj = Person(**person_json)
                except Exception:
                    person_obj = person_json
                people_list.append(person_obj)

            if any(r[0] != first_jurisdiction for r in rows):
                print(
                    f"Warning: multiple jurisdictions matched point; using first {first_jurisdiction}"
                )
            # primary predicate is ST_Intersects

            return {"jurisdiction_ocdid": first_jurisdiction, "people": people_list}
    except Exception as e:
        print(f"Error in get_people_by_geo: {e}")
        return []
    
async def get_geojson_by_latlong(lat: float, long: float, zoom: int = None):
    """Return multiple GeoJSON geometries from geo for polygons near the given point.
    Includes jurisdiction_ocdid from jurisdictions. If zoom is provided a radius is computed
    (meters) to limit the neighborhood. Results are ordered by distance for performance.
    Note: does not enforce a hard result limit — caller should supply reasonable zoom.
    """
    # compute a buffer in meters based on zoom and latitude; fallback to ~1km when zoom not provided
    if zoom is None:
        buffer_m = 1000.0
    else:
        # meters per pixel at given latitude for WebMercator approximation
        meters_per_pixel = 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)
        # use a neighborhood of ~512 pixels (tunable) but enforce a sensible min
        buffer_m = max(50.0, meters_per_pixel * 512.0)

    try:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    j.jurisdiction_ocdid,
                    g.geoid,
                    ST_AsGeoJSON(g.geom)::json AS geojson,
                    ST_Distance(
                        g.geom::geography,
                        ST_SetSRID(ST_Point(%s, %s), 4326)::geography
                    ) AS distance_m
                FROM geo g
                JOIN jurisdictions j ON j.data->>'geoid' = g.geoid
                WHERE ST_DWithin(
                    g.geom::geography,
                    ST_SetSRID(ST_Point(%s, %s), 4326)::geography,
                    %s
                )
                ORDER BY distance_m;
                """,
                (long, lat, long, lat, buffer_m),
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

    where_clauses = ["state = %s"]
    params = [state.lower()]

    if search_string:
        where_clauses.append("LOWER(data->>'name') LIKE %s")
        params.append(f"%{search_string.lower()}%")

    where_condition = " AND ".join(where_clauses)

    try:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT COUNT(*) FROM jurisdictions WHERE {where_condition};
                """,
                params,
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                f"""
                SELECT jurisdiction_ocdid, data
                FROM jurisdictions
                WHERE {where_condition}
                ORDER BY jurisdiction_ocdid  -- Always use ORDER BY with LIMIT/OFFSET
                LIMIT %s OFFSET %s;
                """,
                (*params, limit, skip),
            )

            # Fetch all matching records
            results = await cur.fetchall()

            # Process the results
            jurisdictions = []
            for row in results:
                jurisdictions.append({"jurisdiction_ocdid": row[0], **row[1]})

            return total_count, jurisdictions

    except Exception as e:
        print(f"Database error in get_jurisdictions: {e}")
        return 0, []

# Jobs

async def list_jobs():
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


async def create_job(
        request_id: str, 
        job_type: str,
        arguments_json: dict):
    async with pool.connection() as conn:
        serialized_arguments = json.dumps(arguments_json)
        await conn.execute(
            """
            INSERT INTO jobs (request_id, job_type, status, progress, arguments_json, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
            """,
            (request_id, job_type, "pending", 0, serialized_arguments),
        )

async def get_job(request_id: str):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT status, progress, arguments_json, result_json, created_at, updated_at FROM jobs
            WHERE request_id = %s;
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
                "result_json": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }
        return {"error": "Job not found"}
    
async def get_job_status(request_id: str):
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
        return {"error": "Job not found"}

async def update_job_status(request_id: str, progress: int, status: str = None):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE jobs
            SET progress = %s, status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE request_id = %s;
            """,
            (progress, status, request_id),
        )
