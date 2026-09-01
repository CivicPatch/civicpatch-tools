"""Database queries for `source_records` — one row per sighting, and who each sighting is.

A row is what one page said about one person, once, verbatim. Write-once: there is deliberately
no update and no delete here.

Nothing derived is stored. `derive_roles` is pure, so storing its answer only means storing one
that goes stale — it runs at read time instead.

Linkage lives in `source_record_identities` rather than on the record, so re-resolving who is
whom never rewrites evidence.
"""

import uuid

from database.database import get_pool

_INSERT_RECORD = """
    INSERT INTO source_records
        (id, changeset_id, jurisdiction_ocdid, name, label, source_url,
         url, phone, email, image, cdn_image, start_date, end_date)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_IDENTITY = """
    INSERT INTO source_record_identities (source_record_id, person_id)
    VALUES (%s, %s)
"""


def _record_row(
    record_id: str, changeset_id: str, jurisdiction_ocdid: str, record: dict
) -> tuple:
    return (
        record_id,
        changeset_id,
        jurisdiction_ocdid,
        record["name"],
        record["label"],
        record["source_url"],
        record.get("url"),
        record.get("phone"),
        record.get("email"),
        record.get("image"),
        record.get("cdn_image"),
        record.get("start_date"),
        record.get("end_date"),
    )


async def insert_source_records(
    changeset_id: str, jurisdiction_ocdid: str, records_by_person: dict[str, list[dict]]
) -> int:
    """Every sighting the scrape saw, and which person each one was resolved to.

    Ids are minted here so both inserts can name the same row without a round trip between
    them. The pair is written in one transaction: a record with no identity would be evidence
    nothing can find.
    """
    sightings = [
        (str(uuid.uuid4()), person_id, record)
        for person_id, records in records_by_person.items()
        for record in records
    ]
    if not sightings:
        return 0

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            _INSERT_RECORD,
            [
                _record_row(record_id, changeset_id, jurisdiction_ocdid, record)
                for record_id, _, record in sightings
            ],
        )
        await cur.executemany(
            _INSERT_IDENTITY,
            [(record_id, person_id) for record_id, person_id, _ in sightings],
        )
    return len(sightings)


async def get_source_records_for_request(changeset_id: str) -> list[dict]:
    """Every sighting one scrape saw, each with the person it was resolved to."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT s.id::text, s.changeset_id::text, i.person_id::text, s.jurisdiction_ocdid,
                   s.name, s.label, s.source_url, s.url, s.phone, s.email,
                   s.image, s.cdn_image, s.start_date, s.end_date, s.created_at
            FROM source_records s
            JOIN source_record_identities i ON i.source_record_id = s.id
            WHERE s.changeset_id = %s
            ORDER BY s.created_at, s.label
            """,
            (changeset_id,),
        )
        columns = [column.name for column in cur.description or []]
        return [dict(zip(columns, row)) for row in await cur.fetchall()]
