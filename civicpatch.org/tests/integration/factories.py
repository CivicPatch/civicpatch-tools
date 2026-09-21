"""Row builders for integration tests, driven through the writers production actually uses.

Runs are why this module exists. A run starts with **no changeset**: `register_run` has no
`changeset_id` parameter at all, and one is minted only at ingest, only on success, by
`register_scrape_changeset`. Tests that hand-rolled
`INSERT INTO pipeline_runs (..., changeset_id)` described a row only migration 169's backfill
ever produced, so readers that broke on real in-flight runs stayed green — see
`test_a_run_in_flight_has_no_changeset_yet`.

Going through the real writers is the point: a fixture that restates the schema is a second,
unenforced claim about it, and it drifts the moment the writer changes.

Backdating is the one thing done in raw SQL. Windows are a test concern; production never moves
a row through time.
"""

import json
import uuid

from core.membership_proposal import ids_by_person_and_organization
from core.post_derivation import DerivedMembership, MembershipBinding
from database import memberships, organizations, projection
from database.changesets import register_scrape_changeset
from database.database import get_pool
from database.pipeline_runs import register_run, update_pipeline_run_status
from database.source_records import insert_source_records
from shared.utils.statuses import PipelineRunStatus


async def seed_jurisdiction(
    jurisdiction_ocdid: str, state: str, name: str = "Zy Place"
) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, %s, %s::jsonb, now())
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (jurisdiction_ocdid, state, f'{{"name": "{name}"}}'),
        )
        await conn.commit()


async def start_run(
    jurisdiction_ocdid: str,
    *,
    status: PipelineRunStatus = PipelineRunStatus.INIT,
    progress: int = 0,
    created_by_user_id: str | None = None,
) -> str:
    """An attempt in flight: no changeset, no `finished_at`, exactly as production starts one."""
    run_id = str(uuid.uuid4())
    await register_run(
        run_id, jurisdiction_ocdid, {}, created_by_user_id, status, progress
    )
    return run_id


async def fail_run(run_id: str) -> None:
    """A run that died. It reaches no ingest, so it mints no changeset and is in no proposal count."""
    await update_pipeline_run_status(run_id, PipelineRunStatus.ERROR.value)


async def complete_run(run_id: str) -> str:
    """A run that reached ingest: mint the proposal, link it, then report the terminal status."""
    changeset_id = await register_scrape_changeset(run_id)
    await update_pipeline_run_status(run_id, PipelineRunStatus.SUCCESS.value)
    return changeset_id


async def backdate_run(run_id: str, days: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE pipeline_runs
            SET created_at = now() - make_interval(days => %s),
                updated_at = now() - make_interval(days => %s)
            WHERE id = %s
            """,
            (days, days, run_id),
        )
        await conn.commit()


async def backdate_changeset(changeset_id: str, days: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE changesets
            SET created_at = now() - make_interval(days => %s),
                updated_at = now() - make_interval(days => %s)
            WHERE id::text = %s
            """,
            (days, days, changeset_id),
        )
        await conn.commit()


async def collect_and_publish(jurisdiction_ocdid: str, collected_at) -> str:
    """A published collection changeset dated `collected_at` — what makes a jurisdiction fresh.

    Freshness used to be `jurisdictions.scraped_at`, a column a fixture could just set. It is
    derived now — `max(updated_at)` over published collection changesets — so a fixture has to
    produce the thing it derives from rather than the cache of it.

    The run and the changeset come from the real writers; only the dates are raw SQL, the same
    licence `backdate_run` takes. Pass `collected_at=None` for a jurisdiction that has been
    collected but never published, which is a different fixture from never collected at all.
    """
    run_id = await start_run(jurisdiction_ocdid)
    changeset_id = await complete_run(run_id)
    if collected_at is None:
        return changeset_id
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE changesets SET published_at = now(), updated_at = %s WHERE id::text = %s",
            (collected_at, changeset_id),
        )
    return changeset_id


async def bind_membership(
    cur, member: DerivedMembership, post_id: str, organization_id: str, last_seen_at
) -> str:
    """One membership, written by the same steps publish runs. Returns its id."""
    bindings = [
        MembershipBinding(
            member=member, organization_id=organization_id, post_id=post_id
        )
    ]
    await memberships.close_moved_memberships(cur, bindings, last_seen_at)
    await projection.upsert_open_memberships(
        cur, bindings, last_seen_at, advances_last_seen=True
    )
    jurisdiction_ocdid = await organizations.jurisdiction_for(cur, organization_id)
    assert jurisdiction_ocdid is not None
    membership_ids = ids_by_person_and_organization(
        await memberships.open_memberships(cur, [jurisdiction_ocdid])
    )
    await projection.replace_membership_roles(cur, bindings, membership_ids)
    return membership_ids[(member.person_id, organization_id)]


async def default_organization(cur, jurisdiction_ocdid: str) -> str:
    """The jurisdiction's default organization, created when a raw-inserted jurisdiction has none."""
    await cur.execute(
        """
        SELECT id::text FROM organizations WHERE jurisdiction_ocdid = %s
        ORDER BY meta_is_default DESC, sort_order, name LIMIT 1
        """,
        (jurisdiction_ocdid,),
    )
    row = await cur.fetchone()
    if row:
        return row[0]
    return await organizations.find_or_create(cur, jurisdiction_ocdid)


async def published_scrape(
    jurisdiction_ocdid: str, at, records: dict[str, list[dict]]
) -> str:
    """A published scrape changeset dated `at`, and its source records keyed by person id, each
    with its identity row. What has to exist before a person exists to the fold. Returns the
    changeset id."""
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO changesets "
            "  (id, jurisdiction_ocdid, kind, created_at, updated_at, published_at) "
            "VALUES (%s, %s, 'scrape', %s, %s, %s)",
            (changeset_id, jurisdiction_ocdid, at, at, at),
        )
    await insert_source_records(changeset_id, jurisdiction_ocdid, records)
    return changeset_id


async def published_source_record(
    jurisdiction_ocdid: str,
    organization_id: str,
    person_id: str,
    name: str,
    label: str,
    page: str,
    at,
    **fields,
) -> str:
    """One person's record from one page, under its own published scrape. `fields` is whatever
    else the page said (`phone`, `other_names`, ...)."""
    return await published_scrape(
        jurisdiction_ocdid,
        at,
        {
            person_id: [
                {
                    "name": name,
                    "label": label,
                    "source_url": page,
                    "url": page,
                    "organization_id": organization_id,
                    **fields,
                }
            ]
        },
    )


def sources_of(labels: list[str]) -> str:
    """`memberships.sources` for labels with no page, as jsonb text for a raw insert."""
    return json.dumps([{"url": None, "note": label} for label in labels])
