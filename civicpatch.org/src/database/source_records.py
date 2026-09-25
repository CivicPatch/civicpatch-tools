"""Database queries for `source_records` — one row per sighting, and who each sighting is.

A row is what one page said about one person, once, verbatim. Write-once: there is deliberately
no update and no delete here.

Nothing derived is stored. `derive_roles` is pure, so storing its answer only means storing one
that goes stale — it runs at read time instead.

`person_id` is the matcher's answer at ingest and is never rewritten: a re-link is a
`source_record` / `person_id` claim, read by the fold.
"""

import uuid

from database.database import get_pool

_INSERT_RECORD = """
    INSERT INTO source_records
        (id, changeset_id, jurisdiction_ocdid, name, other_names, label, source_url,
         url, phone, email, image, cdn_image, start_date, end_date, organization_id, person_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _record_row(
    record_id: str, changeset_id: str, jurisdiction_ocdid: str, person_id: str, record: dict
) -> tuple:
    return (
        record_id,
        changeset_id,
        jurisdiction_ocdid,
        record["name"],
        record.get("other_names") or [],
        record["label"],
        record["source_url"],
        record.get("url"),
        record.get("phone"),
        record.get("email"),
        record.get("image"),
        record.get("cdn_image"),
        record.get("start_date"),
        record.get("end_date"),
        record.get("organization_id"),
        person_id,
    )


async def organizations_for_changeset(cur, changeset_id: str) -> list[str]:
    """Which bodies this changeset read a page for. A body with no record here was not looked at,
    so publishing must not retire anyone in it."""
    await cur.execute(
        "SELECT DISTINCT organization_id::text FROM source_records WHERE changeset_id = %s",
        (changeset_id,),
    )
    return [row[0] for row in await cur.fetchall()]


_CHANGESET_IMAGES = """
    SELECT DISTINCT cdn_image FROM source_records
    WHERE changeset_id = %s AND cdn_image IS NOT NULL AND cdn_image <> ''
"""


async def changeset_images(changeset_id: str) -> list[str]:
    """The artifact photos this changeset's records brought, for publish to promote."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(_CHANGESET_IMAGES, (changeset_id,))
        return [row[0] for row in await cur.fetchall()]


async def insert_source_records(
    changeset_id: str, jurisdiction_ocdid: str, records_by_person: dict[str, list[dict]]
) -> int:
    """Every sighting the scrape saw, and which person each one was resolved to."""
    rows = [
        _record_row(str(uuid.uuid4()), changeset_id, jurisdiction_ocdid, person_id, record)
        for person_id, records in records_by_person.items()
        for record in records
    ]
    if not rows:
        return 0

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(_INSERT_RECORD, rows)
    return len(rows)


async def get_source_records_for_changeset(changeset_id: str) -> list[dict]:
    """Every sighting one scrape saw, each with the person it was resolved to."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT s.id::text, s.changeset_id::text, s.person_id::text, s.jurisdiction_ocdid,
                   s.name, s.other_names, s.label, s.source_url, s.url, s.phone, s.email,
                   s.image, s.cdn_image, s.start_date, s.end_date, s.created_at,
                   s.organization_id::text AS organization_id
            FROM source_records s
            WHERE s.changeset_id = %s
            ORDER BY s.created_at, s.label
            """,
            (changeset_id,),
        )
        columns = [column.name for column in cur.description or []]
        return [dict(zip(columns, row)) for row in await cur.fetchall()]
