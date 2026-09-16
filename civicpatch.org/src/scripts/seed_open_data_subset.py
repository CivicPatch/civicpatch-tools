"""Populate the local dev database with a small subset of the published open-data dataset.

Each table comes from where production gets it. Jurisdictions come from the open-data repo, read
through the same sync code production runs (which also gives each one its default organization),
from a single public archive download rather than the authenticated GitHub API. Everything
`civicpatch.org` itself owns comes from its public Parquet export at
`https://cdn.civicpatch.org/parquet/` (the dataset the open-data.civicpatch.org SQL explorer
queries): `divisions` in full, optionally narrowed to specific states, and `organizations` plus
everything that hangs off one (`posts`, `memberships`, the `people` those reference) capped by
`--limit`, since those are the tables that actually grow with real content. No GitHub App
credentials, no Temporal worker, just real production data to click around in.

Run via `mise run seed-dev-data` (see `mise.toml`), which execs this inside the running
`civicpatch-org` container.

**Destructive.** Every run wipes the tables it is about to repopulate first — see
`wipe_existing_data` — rather than merging with whatever a dev's database already holds. Real
production ids collide with existing local rows more often than a fresh-DB assumption allows for
(the id itself matches by luck, but a *different* unique constraint — an organization's own
`(jurisdiction_ocdid, name)`, say — does not), and an `ON CONFLICT DO NOTHING` cannot recover
from a collision it did not target. Intended only for a local dev database.
"""

import argparse
import asyncio
import io
import logging
import tarfile
from datetime import datetime, timezone
from typing import Any, LiteralString

import httpx
import pyarrow.parquet as pq
from psycopg import AsyncConnection

from core.sources.open_data.paths import SyncFileKind, classify_path, jurisdiction_path_parts
from database.database import get_pool
from services.sources.open_data import read_jurisdiction_files

logger = logging.getLogger(__name__)

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


def files_in_states(files: dict[str, str], states: set[str] | None) -> list[str]:
    if states is None:
        return list(files)
    return [path for path in files if jurisdiction_path_parts(path)[0] in states]


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
    return {
        "id": row["id"],
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


def membership_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "post_id": row["post_id"],
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
        "source_labels": row["source_labels"],
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
             first_seen_at, last_seen_at, closed_at, created_at, designations, source_labels)
        VALUES
            (%(id)s, %(post_id)s, %(organization_id)s, %(person_id)s, %(label)s, %(start_date)s,
             %(end_date)s, %(first_seen_at)s, %(last_seen_at)s, %(closed_at)s, %(created_at)s,
             %(designations)s, %(source_labels)s)
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
    changesets, assertions, pipeline_runs, and so on — cascades from these five roots.

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


async def seed(states: list[str] | None, limit: int) -> None:
    """`jurisdictions` and `divisions` load in full (optionally narrowed by `states`) — pure
    geography, cheap regardless of size. `limit` caps how many `organizations` load, and
    everything that hangs off one — `posts`, `memberships`, and the `people` those memberships
    reference — is scoped to just that limited set rather than to the full jurisdiction list."""
    state_set = {state.lower() for state in states} if states else None
    pool = await get_pool()

    async with httpx.AsyncClient(timeout=120) as client, pool.connection() as conn:
        await wipe_existing_data(conn)

        role_rows = [role_row(row) for row in await fetch_table(client, "roles")]
        await insert_ignoring_conflicts(conn, "roles", role_rows)
        logger.info("seed_open_data_subset: roles: %d row(s)", len(role_rows))

        files = jurisdiction_files(await fetch_open_data_archive(client))

        async def read_file(path: str) -> tuple[str, str]:
            return path, files[path]

        synced = await read_jurisdiction_files(
            files_in_states(files, state_set), datetime.now(timezone.utc), read_file
        )
        jurisdiction_ocdids = await loaded_jurisdiction_ocdids(conn)
        logger.info(
            "seed_open_data_subset: jurisdictions: %d from %d file(s)",
            len(jurisdiction_ocdids),
            len(synced),
        )

        raw_divisions = await fetch_table(client, "divisions")
        division_rows = [
            division_row(row)
            for row in rows_in_jurisdictions(raw_divisions, jurisdiction_ocdids)
        ]
        await insert_ignoring_conflicts(conn, "divisions", division_rows)
        logger.info("seed_open_data_subset: divisions: %d row(s)", len(division_rows))

        raw_organizations = await fetch_table(client, "organizations")
        organizations_in_scope = rows_in_jurisdictions(raw_organizations, jurisdiction_ocdids)[
            :limit
        ]
        organization_ids = {row["id"] for row in organizations_in_scope}
        organization_rows = [organization_row(row) for row in organizations_in_scope]
        await remove_synced_defaults(
            conn, {row["jurisdiction_ocdid"] for row in organizations_in_scope}
        )
        await insert_ignoring_conflicts(conn, "organizations", organization_rows)
        logger.info("seed_open_data_subset: organizations: %d row(s)", len(organization_rows))

        raw_posts = await fetch_table(client, "posts")
        posts_in_scope = [row for row in raw_posts if row["organization_id"] in organization_ids]
        post_rows = [post_row(row) for row in posts_in_scope]
        await insert_ignoring_conflicts(conn, "posts", post_rows)
        logger.info("seed_open_data_subset: posts: %d row(s)", len(post_rows))

        # Fetched before `people` so the person set can be narrowed to just who these
        # memberships actually reference, but inserted after — memberships FK both ways.
        raw_memberships = await fetch_table(client, "memberships")
        memberships_in_scope = [
            row for row in raw_memberships if row["organization_id"] in organization_ids
        ]
        person_ids = {row["person_id"] for row in memberships_in_scope}

        raw_people = await fetch_table(client, "people")
        person_rows = [person_row(row) for row in raw_people if row["id"] in person_ids]
        await insert_ignoring_conflicts(conn, "people", person_rows)
        logger.info("seed_open_data_subset: people: %d row(s)", len(person_rows))

        membership_rows = [membership_row(row) for row in memberships_in_scope]
        await insert_ignoring_conflicts(conn, "memberships", membership_rows)
        logger.info("seed_open_data_subset: memberships: %d row(s)", len(membership_rows))


DEFAULT_LIMIT = 10


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--states",
        default=None,
        help="Comma-separated state postal codes to narrow jurisdictions to (default: any state)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Maximum number of organizations (and what hangs off them) to load (default: %(default)s)",
    )
    args = parser.parse_args()
    states = (
        [state.strip() for state in args.states.split(",") if state.strip()]
        if args.states
        else None
    )
    asyncio.run(seed(states, args.limit))


if __name__ == "__main__":
    main()
