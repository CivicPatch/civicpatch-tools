"""The public entity graph, one query per table — the rows `roster_parquet` writes.

Every column is named. `SELECT *` would make the published schema whatever the table happens to
hold that week — a consumer's query breaks silently when a column is inserted or renamed, and
anything added to a table would be published without anyone deciding to. The list is the
contract, the same job `HEADERS` does for the sheet.

Deliberately left out, and why:

  posts._headcount, posts._is_tracked   internal, underscore-prefixed by their own author
  jurisdictions.search_text             a search index, not a fact about the place
  jurisdictions.data                    the raw synced blob; `name` is lifted out of it instead

UUIDs are cast to text here rather than in the writer, per the project's rule that the database
layer owns the type contract. It also happens to be what parquet wants: pyarrow has no native
UUID, and would otherwise infer an opaque struct.

**One file per table, not one per state.** Partitioning was measured to cost more than it saved.
`memberships` is 1.5 MB in total, and split thirteen ways a full-table scan had to open thirteen
files — a footer read plus column-chunk reads each — where one file needs about five requests.
DuckDB reads parquet over HTTP by range, so it never fetches a column or a row group the query
does not want; `state` as a real column, with rows ordered by it, prunes *inside* one file the
way a partition path did across many. Worth revisiting only when a table reaches tens of MB,
where the per-file footer stops dominating.

That is why every query below carries `state` and orders by it: the ordering is what puts each
state in contiguous row groups, and a row group is the unit a reader can skip.
"""

from typing import Any, LiteralString

from database.database import get_pool

# `state` is not stored on most of these tables — it is the third segment of the ocdid, itself
# prefixed (`ocd-jurisdiction/country:us/state:wa/...` → `state:wa` → `wa`).
_STATE_OF = "split_part(split_part({col}, '/', 3), ':', 2)"

GLOBAL_TABLES = ("roles",)

# `LiteralString`, not `str`: psycopg only accepts a literal, which is what keeps a table name
# from ever being composed from input. The registry is the only place SQL is written here.
TABLES: dict[str, LiteralString] = {
    "people": f"""
        -- Both images: `image` is where the photo came from, `cdn_image` is the copy we serve.
        -- Provenance and delivery are different facts, and a consumer checking our rendering
        -- against the source needs the first.
        SELECT {_STATE_OF.format(col="jurisdiction_ocdid")} AS state,
               id::text, jurisdiction_ocdid, name, other_names, emails, phones, urls,
               source_urls, image, cdn_image, updated_at
        FROM people
        ORDER BY state, id
    """,
    "memberships": f"""
        SELECT {_STATE_OF.format(col="p.jurisdiction_ocdid")} AS state,
               m.id::text, m.person_id::text, m.post_id::text, m.organization_id::text,
               p.jurisdiction_ocdid,
               m.label, m.start_date, m.end_date,
               m.first_seen_at, m.last_seen_at, m.closed_at, m.created_at,
               m.designations, m.source_labels,
               (m.closed_at IS NULL) AS is_open
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        ORDER BY state, m.id
    """,
    "posts": f"""
        SELECT {_STATE_OF.format(col="jurisdiction_ocdid")} AS state,
               id::text, jurisdiction_ocdid, organization_id::text, role_id, division_ocdid,
               created_at
        FROM posts
        ORDER BY state, id
    """,
    "organizations": f"""
        SELECT {_STATE_OF.format(col="jurisdiction_ocdid")} AS state,
               id::text, jurisdiction_ocdid, name, sort_order, created_at
        FROM organizations
        ORDER BY state, id
    """,
    "divisions": f"""
        SELECT {_STATE_OF.format(col="jurisdiction_ocdid")} AS state,
               ocdid, jurisdiction_ocdid, created_at
        FROM divisions
        ORDER BY state, ocdid
    """,
    "jurisdictions": """
        -- The one table with a real `state` column; no need to cut it out of the ocdid.
        SELECT state, jurisdiction_ocdid, level, status,
               data->>'name' AS name,
               parent_ocdids, updated_at
        FROM jurisdictions
        ORDER BY state, jurisdiction_ocdid
    """,
    "roles": """
        -- Global: a role names no jurisdiction, so it carries no state.
        SELECT id, label, status, is_unique, priority, created_at
        FROM roles
        ORDER BY id
    """,
}


async def rows(table: str) -> list[dict[str, Any]]:
    """One table, whole.

    Materialised rather than streamed: parquet is written whole — the format's footer can only
    be built once every row group is known — so there is nothing to hand a stream to. The
    largest table here is 21k rows.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(TABLES[table])
        columns = [c.name for c in cur.description or []]
        return [dict(zip(columns, row)) for row in await cur.fetchall()]
