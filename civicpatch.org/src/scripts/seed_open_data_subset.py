"""Populate the local dev database with a small subset of the published open-data dataset.

Each table comes from where production gets it. Jurisdictions come from the open-data repo, read
through the same sync code production runs (which also gives each one its default organization),
from a single public archive download rather than the authenticated GitHub API. Everything
`civicpatch.org` itself owns comes from its public Parquet export at
`https://cdn.civicpatch.org/parquet/` (the dataset the open-data.civicpatch.org SQL explorer
queries): every jurisdiction and division, and `organizations` plus everything that hangs off
one (`posts`, `memberships`, the `people` those reference) capped by `--limit`, since those are
the tables that actually grow with real content. No GitHub App credentials, no Temporal worker,
just real production data to click around in.

Run via `mise run seed-dev-data` (see `mise.toml`), which execs this inside the running
`civicpatch-org` container.

**Destructive.** Every run wipes the tables it is about to repopulate — see
`wipe_existing_data`, which runs only once every download has succeeded — rather than merging
with whatever a dev's database already holds. Real production ids collide with existing local
rows more often than a fresh-DB assumption allows for (the id itself matches by luck, but a
*different* unique constraint — an organization's own `(jurisdiction_ocdid, name)`, say — does
not), and an `ON CONFLICT DO NOTHING` cannot recover from a collision it did not target. Intended only for a local dev database.
"""

import argparse
import asyncio
import io
import json
import logging
import tarfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, LiteralString

import httpx
import pyarrow.parquet as pq
from psycopg import AsyncConnection
from pydantic import BaseModel

from core.projection.facts import PostKey
from core.sources.open_data.paths import SyncFileKind, classify_path
from database.database import get_pool
from services.sources.open_data import read_jurisdiction_files

logger = logging.getLogger(__name__)

# The export carries `people` and `memberships` but no records, and the fold derives people from
# records. Migration 215 gives record-less rosters their records and is idempotent, so the seed
# runs it again over what it just loaded rather than keeping a copy of it.
BACKFILL_MIGRATION = (
    Path(__file__).parents[2] / "database_operations/migrations/215_backfill_source_records.up.sql"
)

DATA_BASE = "https://cdn.civicpatch.org/parquet/"
# The whole public repo as one download: the REST API allows 60 unauthenticated requests an hour,
# and a sync reads one file per (state, level).
OPEN_DATA_ARCHIVE = "https://codeload.github.com/civicpatch/open-data/tar.gz/refs/heads/main"


async def fetch_table(client: httpx.AsyncClient, table: str) -> list[dict[str, Any]]:
    response = await client.get(f"{DATA_BASE}{table}/data.parquet")
    response.raise_for_status()
    return pq.read_table(io.BytesIO(response.content)).to_pylist()


async def fetch_open_data_archive(client: httpx.AsyncClient) -> bytes:
    response = await client.get(OPEN_DATA_ARCHIVE, follow_redirects=True)
    response.raise_for_status()
    return response.content


def jurisdiction_files(archive: bytes) -> dict[str, str]:
    """Repo path → contents for every `jurisdictions.yml` the sync would read. The archive nests
    everything under one `<repo>-<branch>/` directory, which the repo's own paths do not have."""
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            path = member.name.partition("/")[2]
            extracted = tar.extractfile(member) if member.isfile() else None
            if extracted and classify_path(path) is SyncFileKind.JURISDICTIONS:
                files[path] = extracted.read().decode("utf-8")
    return files


def rows_in_jurisdictions(
    rows: list[dict[str, Any]], jurisdiction_ocdids: set[str]
) -> list[dict[str, Any]]:
    """`divisions` and `organizations` both carry `jurisdiction_ocdid` directly. Filtering on
    the actual set of jurisdictions this run loaded — rather than re-deriving each row's
    `state` independently, the way the export computes it for filtering there — is what keeps
    a table's subset referring only to jurisdictions this run actually inserted."""
    return [row for row in rows if row["jurisdiction_ocdid"] in jurisdiction_ocdids]


# One pure transform per table: a parquet row in, an insert-ready row out. Each drops the
# export's derived `state` column (not a real column on any of these tables) and anything
# else the live schema does not have a column for.


def role_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "status": row["status"],
        "is_unique": row["is_unique"],
        "priority": row["priority"],
        "created_at": row["created_at"],
    }


def role_alias_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "role_id": row["role_id"],
        "label": row["label"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def division_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ocdid": row["ocdid"],
        "jurisdiction_ocdid": row["jurisdiction_ocdid"],
        "created_at": row["created_at"],
    }


def organization_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "jurisdiction_ocdid": row["jurisdiction_ocdid"],
        "name": row["name"],
        "sort_order": row["sort_order"],
        "url": row["url"],
        # Absent from an export written before migration 202's column was added to it.
        "meta_is_default": row.get("meta_is_default", False),
        "created_at": row["created_at"],
    }


def post_row(row: dict[str, Any]) -> dict[str, Any]:
    # Exports from before 218 carry random ids; the id is the key's now.
    return {
        "id": post_id_of(row),
        "jurisdiction_ocdid": row["jurisdiction_ocdid"],
        "organization_id": row["organization_id"],
        "role_id": row["role_id"],
        "division_ocdid": row["division_ocdid"],
        "created_at": row["created_at"],
    }


def person_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "jurisdiction_ocdid": row["jurisdiction_ocdid"],
        "name": row["name"],
        "other_names": row["other_names"],
        "emails": row["emails"],
        "phones": row["phones"],
        "urls": row["urls"],
        "source_urls": row["source_urls"],
        "image": row["image"],
        "cdn_image": row["cdn_image"],
        "updated_at": row["updated_at"],
    }


def post_id_of(post: dict[str, Any]) -> str:
    return PostKey(
        organization_id=post["organization_id"],
        role_id=post["role_id"],
        division_ocdid=post["division_ocdid"],
    ).post_id


def membership_row(row: dict[str, Any], post_ids: dict[str, str]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "post_id": post_ids[row["post_id"]],
        "organization_id": row["organization_id"],
        "person_id": row["person_id"],
        "label": row["label"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "closed_at": row["closed_at"],
        "created_at": row["created_at"],
        "designations": row["designations"],
        # The export has labels without pages; the page is unknown here, as for 206's backfill.
        "sources": json.dumps([{"url": None, "note": label} for label in row["source_labels"]]),
    }


# One literal statement per table — never composed from a variable table/column name, per the
# project's rule that psycopg only accepts a `LiteralString` so that can never happen by
# accident. `%(name)s` placeholders bind directly against each transform's dict keys.
INSERT_SQL: dict[str, LiteralString] = {
    "roles": """
        INSERT INTO roles (id, label, status, is_unique, priority, created_at)
        VALUES (%(id)s, %(label)s, %(status)s, %(is_unique)s, %(priority)s, %(created_at)s)
        ON CONFLICT (id) DO NOTHING
    """,
    "role_aliases": """
        INSERT INTO role_aliases (id, role_id, label, status, created_at)
        VALUES (%(id)s, %(role_id)s, %(label)s, %(status)s, %(created_at)s)
        ON CONFLICT DO NOTHING
    """,
    "divisions": """
        INSERT INTO divisions (ocdid, jurisdiction_ocdid, created_at)
        VALUES (%(ocdid)s, %(jurisdiction_ocdid)s, %(created_at)s)
        ON CONFLICT (ocdid) DO NOTHING
    """,
    "organizations": """
        INSERT INTO organizations
            (id, jurisdiction_ocdid, name, sort_order, url, meta_is_default, created_at)
        VALUES
            (%(id)s, %(jurisdiction_ocdid)s, %(name)s, %(sort_order)s, %(url)s,
             %(meta_is_default)s, %(created_at)s)
        -- No conflict target: `organizations_jurisdiction_ocdid_name_key` (jurisdiction_ocdid,
        -- name) can collide independently of the id PK when a jurisdiction's default org
        -- already exists locally. A bare DO NOTHING guards every unique constraint on the
        -- table, not just the one named.
        ON CONFLICT DO NOTHING
    """,
    "posts": """
        INSERT INTO posts (id, jurisdiction_ocdid, organization_id, role_id, division_ocdid, created_at)
        VALUES
            (%(id)s, %(jurisdiction_ocdid)s, %(organization_id)s, %(role_id)s, %(division_ocdid)s,
             %(created_at)s)
        -- No conflict target: `posts_identity_uq` (organization_id, role_id, division_ocdid)
        -- can collide independently of the id PK — same reasoning as organizations above.
        ON CONFLICT DO NOTHING
    """,
    "people": """
        INSERT INTO people
            (id, jurisdiction_ocdid, name, other_names, emails, phones, urls, source_urls,
             image, cdn_image, updated_at)
        VALUES
            (%(id)s, %(jurisdiction_ocdid)s, %(name)s, %(other_names)s, %(emails)s, %(phones)s,
             %(urls)s, %(source_urls)s, %(image)s, %(cdn_image)s, %(updated_at)s)
        ON CONFLICT (id) DO NOTHING
    """,
    "memberships": """
        INSERT INTO memberships
            (id, post_id, organization_id, person_id, label, start_date, end_date,
             first_seen_at, last_seen_at, closed_at, created_at, designations, sources)
        VALUES
            (%(id)s, %(post_id)s, %(organization_id)s, %(person_id)s, %(label)s, %(start_date)s,
             %(end_date)s, %(first_seen_at)s, %(last_seen_at)s, %(closed_at)s, %(created_at)s,
             %(designations)s, %(sources)s::jsonb)
        -- No conflict target: `memberships_one_open_per_organization` (person_id,
        -- organization_id) WHERE closed_at IS NULL can collide independently of the id PK —
        -- same reasoning as organizations above.
        ON CONFLICT DO NOTHING
    """,
}


# Rows land on real production ids/ocdids, so `ON CONFLICT DO NOTHING` is only a defensive
# backstop here — `wipe_existing_data` runs first on every invocation, so these tables are
# always empty by the time an insert reaches them.
async def insert_ignoring_conflicts(
    conn: AsyncConnection, table: str, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    async with conn.cursor() as cur:
        await cur.executemany(INSERT_SQL[table], rows)
    await conn.commit()


async def wipe_existing_data(conn: AsyncConnection) -> None:
    """Clears every table this script is about to repopulate, plus the two that hold state
    keyed to it without an enforced FK (`review_sessions`/`activity` reference jurisdictions and
    changesets by plain text, not a foreign key, so they survive a cascade and would otherwise
    point at ids this run just erased). Everything else — organizations, posts, memberships,
    changesets, claims, pipeline_runs, and so on — cascades from these five roots.

    Deliberate: an `ON CONFLICT DO NOTHING` insert cannot recover from a dev database that
    already holds *different* rows colliding on a constraint other than the one it targets (a
    jurisdiction's default organization, matched by `(jurisdiction_ocdid, name)` rather than by
    id, say) — see the module docstring."""
    async with conn.cursor() as cur:
        await cur.execute(
            "TRUNCATE jurisdictions, people, roles, review_sessions, activity CASCADE"
        )
    await conn.commit()


async def loaded_jurisdiction_ocdids(conn: AsyncConnection) -> set[str]:
    async with conn.cursor() as cur:
        await cur.execute("SELECT jurisdiction_ocdid FROM jurisdictions")
        return {row[0] for row in await cur.fetchall()}


async def jurisdiction_ocdids_in_states(conn: AsyncConnection, states: list[str]) -> set[str]:
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid FROM jurisdictions WHERE state = ANY(%s)", (states,)
        )
        return {row[0] for row in await cur.fetchall()}


async def remove_synced_defaults(conn: AsyncConnection, jurisdiction_ocdids: set[str]) -> None:
    """The sync gave every jurisdiction an empty 'Government'. Where the export has the real
    bodies, that placeholder would take the name first and leave the exported one skipped by its
    conflict clause — and every exported post pointing at that id failing its foreign key."""
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM organizations WHERE jurisdiction_ocdid = ANY(%s)",
            (list(jurisdiction_ocdids),),
        )
    await conn.commit()


class Downloads(BaseModel):
    """Every table this run loads, fetched before anything is wiped."""

    roles: list[dict[str, Any]]
    role_aliases: list[dict[str, Any]]
    jurisdiction_files: dict[str, str]
    divisions: list[dict[str, Any]]
    organizations: list[dict[str, Any]]
    posts: list[dict[str, Any]]
    memberships: list[dict[str, Any]]
    people: list[dict[str, Any]]


async def download(client: httpx.AsyncClient) -> Downloads:
    archive = await fetch_open_data_archive(client)
    roles, aliases, divisions, organizations, posts, memberships, people = await asyncio.gather(
        fetch_table(client, "roles"),
        fetch_table(client, "role_aliases"),
        fetch_table(client, "divisions"),
        fetch_table(client, "organizations"),
        fetch_table(client, "posts"),
        fetch_table(client, "memberships"),
        fetch_table(client, "people"),
    )
    return Downloads(
        roles=roles,
        role_aliases=aliases,
        jurisdiction_files=jurisdiction_files(archive),
        divisions=divisions,
        organizations=organizations,
        posts=posts,
        memberships=memberships,
        people=people,
    )


async def load_roles(conn: AsyncConnection, downloads: Downloads) -> None:
    role_rows = [role_row(row) for row in downloads.roles]
    await insert_ignoring_conflicts(conn, "roles", role_rows)
    logger.info("seed_open_data_subset: roles: %d row(s)", len(role_rows))

    # After roles: an alias's role must exist. The roles truncate cascades to these.
    alias_rows = [role_alias_row(row) for row in downloads.role_aliases]
    await insert_ignoring_conflicts(conn, "role_aliases", alias_rows)
    logger.info("seed_open_data_subset: role_aliases: %d row(s)", len(alias_rows))


async def load_places(conn: AsyncConnection, downloads: Downloads) -> set[str]:
    """Every jurisdiction, through the production sync, then their divisions. Returns the ocdids."""
    files = downloads.jurisdiction_files

    async def read_file(path: str) -> tuple[str, str]:
        return path, files[path]

    synced = await read_jurisdiction_files(list(files), datetime.now(timezone.utc), read_file)
    jurisdiction_ocdids = await loaded_jurisdiction_ocdids(conn)
    logger.info(
        "seed_open_data_subset: jurisdictions: %d from %d file(s)",
        len(jurisdiction_ocdids),
        len(synced),
    )

    division_rows = [
        division_row(row)
        for row in rows_in_jurisdictions(downloads.divisions, jurisdiction_ocdids)
    ]
    await insert_ignoring_conflicts(conn, "divisions", division_rows)
    logger.info("seed_open_data_subset: divisions: %d row(s)", len(division_rows))
    return jurisdiction_ocdids


async def load_rosters(
    conn: AsyncConnection,
    downloads: Downloads,
    jurisdiction_ocdids: set[str],
    limit: int | None,
) -> None:
    """Up to `limit` organizations (all when None), and the posts, people and memberships —
    closed ones included — that hang off them."""
    organizations_in_scope = rows_in_jurisdictions(downloads.organizations, jurisdiction_ocdids)[
        :limit
    ]
    organization_ids = {row["id"] for row in organizations_in_scope}
    organization_rows = [organization_row(row) for row in organizations_in_scope]
    await remove_synced_defaults(
        conn, {row["jurisdiction_ocdid"] for row in organizations_in_scope}
    )
    await insert_ignoring_conflicts(conn, "organizations", organization_rows)
    logger.info("seed_open_data_subset: organizations: %d row(s)", len(organization_rows))

    posts_in_scope = [row for row in downloads.posts if row["organization_id"] in organization_ids]
    post_rows = [post_row(row) for row in posts_in_scope]
    post_ids = {row["id"]: post_id_of(row) for row in posts_in_scope}
    await insert_ignoring_conflicts(conn, "posts", post_rows)
    logger.info("seed_open_data_subset: posts: %d row(s)", len(post_rows))

    # People narrowed to who these memberships reference, and inserted first: memberships FK them.
    memberships_in_scope = [
        row for row in downloads.memberships if row["organization_id"] in organization_ids
    ]
    person_ids = {row["person_id"] for row in memberships_in_scope}
    person_rows = [person_row(row) for row in downloads.people if row["id"] in person_ids]
    await insert_ignoring_conflicts(conn, "people", person_rows)
    logger.info("seed_open_data_subset: people: %d row(s)", len(person_rows))

    membership_rows = [membership_row(row, post_ids) for row in memberships_in_scope]
    await insert_ignoring_conflicts(conn, "memberships", membership_rows)
    logger.info("seed_open_data_subset: memberships: %d row(s)", len(membership_rows))


async def seed(states: list[str], limit: int | None) -> None:
    """`jurisdictions` and `divisions` load in full — pure geography, cheap regardless of size.
    `states`, when given, narrows which jurisdictions' `organizations` load, and `limit` caps how
    many; everything that hangs off one — `posts`, `memberships`, and the `people` those
    memberships reference — is scoped to that set.

    Everything is downloaded before the wipe, so a failed download leaves the database as it was.
    """
    pool = await get_pool()

    async with httpx.AsyncClient(timeout=120) as client, pool.connection() as conn:
        downloads = await download(client)
        await wipe_existing_data(conn)
        await load_roles(conn, downloads)
        jurisdiction_ocdids = await load_places(conn, downloads)
        if states:
            jurisdiction_ocdids = await jurisdiction_ocdids_in_states(conn, states)
        await load_rosters(conn, downloads, jurisdiction_ocdids, limit)
        await backfill_source_records(conn)


async def backfill_source_records(conn: AsyncConnection) -> None:
    await conn.commit()
    await conn.set_autocommit(True)
    # The migration file is its own transaction (BEGIN ... COMMIT), and is read from disk, which
    # psycopg's LiteralString typing cannot see through.
    await conn.execute(BACKFILL_MIGRATION.read_text())  # type: ignore[arg-type]
    await conn.set_autocommit(False)
    logger.info("seed_open_data_subset: backfilled source records (migration 215)")


DEFAULT_LIMIT = "10"
NO_LIMIT = "none"


def limit_arg(value: str) -> int | None:
    return None if value == NO_LIMIT else int(value)


def states_arg(value: str) -> list[str]:
    return [state.strip().lower() for state in value.split(",") if state.strip()]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=limit_arg,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of organizations (and what hangs off them) to load, or "
        f"'{NO_LIMIT}' (default: %(default)s)",
    )
    parser.add_argument(
        "--states",
        type=states_arg,
        default=[],
        help="Comma-separated state postal codes whose organizations to load (default: any)",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.states, args.limit))


if __name__ == "__main__":
    main()
