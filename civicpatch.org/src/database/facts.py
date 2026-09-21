"""Loads one jurisdiction's facts for the fold.

The only module that knows how facts are stored. It filters (published changesets, the as-of
cutoff, withdraws never cut) so `core/projection/` can trust what it is handed, and it adapts
today's schema to the shape the resolvers will keep: three of the four adapters below are
deleted by a named step, and nothing in `core/` has to know they existed.
"""

from datetime import datetime

from core.projection.facts import Claim, Facts, SourceRecord
from database.database import get_pool

# Only a published changeset's facts derive (R3). `assertions.changeset_id` is still nullable
# today — a direct field assert or an edit made outside review has none — and those claims are
# live, so they must not be dropped by the join. Step 16 makes the column NOT NULL and this
# becomes a plain inner join.
_PUBLISHED_OR_UNATTRIBUTED = """
    LEFT JOIN changesets ON changesets.id = assertions.changeset_id
    WHERE (
        (assertions.changeset_id IS NULL AND assertions.created_at <= %(as_of)s)
        OR changesets.published_at <= %(as_of)s
    )
"""

_RECORDS = """
    SELECT source_records.id::text, source_records.changeset_id::text,
           source_records.created_at, source_record_identities.person_id::text,
           source_records.organization_id::text, source_records.name, source_records.label,
           source_records.source_url, source_records.other_names, source_records.url,
           source_records.phone, source_records.email, source_records.image,
           source_records.cdn_image, source_records.start_date, source_records.end_date
    FROM source_records
    JOIN changesets ON changesets.id = source_records.changeset_id
    -- Inner join, not left: a record nobody matched names no one, so it can derive no person.
    -- Step 6 moves `person_id` onto the record and deletes this join; its ⚠ is to count the
    -- unmatched rows first, because that count is exactly what this join drops today.
    JOIN source_record_identities
      ON source_record_identities.source_record_id = source_records.id
    WHERE source_records.jurisdiction_ocdid = %(jurisdiction_ocdid)s
      AND changesets.published_at <= %(as_of)s
"""

_PERSON_CLAIMS = f"""
    SELECT assertions.id::text, assertions.changeset_id::text, assertions.created_at,
           assertions.entity_type, assertions.entity_id::text, assertions.field_path,
           assertions.kind, assertions.value
    FROM assertions
    {_PUBLISHED_OR_UNATTRIBUTED}
      AND assertions.entity_type = 'person'
      AND assertions.entity_id::text = ANY(%(person_ids)s)
      -- A withdrawal is still a column, so a withdrawn claim is simply not loaded and
      -- `withdraws` stays empty. Step 5 turns these into `withdraw` rows, and `live_facts`
      -- starts doing the work this line does now.
      AND assertions.withdrawn_at IS NULL
"""


def _record(row: tuple) -> SourceRecord:
    return SourceRecord(
        id=row[0],
        changeset_id=row[1],
        created_at=row[2],
        person_id=row[3],
        organization_id=row[4],
        name=row[5],
        label=row[6],
        source_url=row[7],
        other_names=tuple(row[8] or ()),
        url=row[9],
        phone=row[10],
        email=row[11],
        image=row[12],
        cdn_image=row[13],
        start_date=row[14],
        end_date=row[15],
    )


def _claim(row: tuple) -> Claim:
    return Claim(
        id=row[0],
        changeset_id=row[1],
        created_at=row[2],
        entity_type=row[3],
        entity_id=row[4],
        field_path=row[5],
        kind=row[6],
        value=row[7],
    )


async def load_facts(cur, jurisdiction_ocdid: str, as_of: datetime) -> Facts:
    """Every live fact this jurisdiction's roster derives from, as at `as_of`.

    Membership, post, organization and taxonomy claims join this as their write paths move
    onto the model (steps 7, 10, 11 and 18); until then a person's claims are the only
    judgements the fold reads.

    `reads` stays empty until `source_pages` exists: `core.projection.reads.reads_of` infers a
    read from any live record naming the organization, which is today's rule, and page rows
    will union with that rather than replace it.
    """
    await cur.execute(
        _RECORDS, {"jurisdiction_ocdid": jurisdiction_ocdid, "as_of": as_of}
    )
    records = tuple(_record(row) for row in await cur.fetchall())

    person_ids = sorted({record.person_id for record in records})
    claims: tuple[Claim, ...] = ()
    if person_ids:
        await cur.execute(_PERSON_CLAIMS, {"person_ids": person_ids, "as_of": as_of})
        claims = tuple(_claim(row) for row in await cur.fetchall())

    return Facts(
        records=records,
        claims=claims,
        withdraws=(),
        reads=(),
    )


async def load_facts_for(jurisdiction_ocdid: str, as_of: datetime) -> Facts:
    """`load_facts` on its own connection, for callers outside a transaction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await load_facts(cur, jurisdiction_ocdid, as_of)
