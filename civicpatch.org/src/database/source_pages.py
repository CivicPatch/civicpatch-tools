"""Database queries for `source_pages`: one row per page per run. Write-once, like
`source_records`."""

from core.source_pages import SourcePageRow
from database.database import get_pool
from schemas.claims import EntityType
from shared.schemas import PublishedSourcePage, PersonSourceRecord

# A fact is withdrawn when a live `withdraw` claim points at it (214, 236).
_NOT_WITHDRAWN = """NOT EXISTS (
    SELECT 1 FROM claims
    WHERE claims.kind = 'withdraw' AND claims.entity_type = %(entity_type)s
      AND claims.entity_id = {table}.id AND claim_is_live(claims.id)
)"""

# Per url, the latest row a run may reuse: its changeset published, not withdrawn, hashed,
# and no extraction attempt failed (a page the model struggled with is read fresh).
_PUBLISHED_SOURCE_PAGES = f"""
    SELECT DISTINCT ON (source_pages.source_url)
           source_pages.source_url,
           coalesce(source_pages.unchanged_since_source_page_id, source_pages.id)::text,
           source_pages.page_hash, source_pages.prompt_hash, source_pages.is_relevant,
           source_pages.organization_ids::text[], source_pages.relevant_urls,
           source_pages.changeset_id::text
    FROM source_pages
    JOIN changesets ON changesets.id = source_pages.changeset_id
    WHERE source_pages.jurisdiction_ocdid = %(jurisdiction_ocdid)s
      AND changesets.published_at IS NOT NULL
      AND source_pages.page_hash IS NOT NULL
      AND cardinality(source_pages.heuristics_failures) = 0
      AND {_NOT_WITHDRAWN.format(table="source_pages")}
    ORDER BY source_pages.source_url, source_pages.created_at DESC
"""

_PUBLISHED_RECORDS = f"""
    SELECT source_records.changeset_id::text, source_records.source_url,
           source_records.name, source_records.label, source_records.phone,
           source_records.email, source_records.url, source_records.start_date,
           source_records.end_date, source_records.image, source_records.cdn_image,
           source_records.other_names, source_records.organization_id::text
    FROM source_records
    WHERE source_records.changeset_id::text = ANY(%(changeset_ids)s)
      AND {_NOT_WITHDRAWN.format(table="source_records")}
"""

_INSERT_PAGE = """
    INSERT INTO source_pages
        (source_url, jurisdiction_ocdid, pipeline_run_id, changeset_id, organization_ids,
         page_hash, prompt_hash, cache_path, anchor_text, is_relevant, relevant_urls,
         heuristics_failures, unchanged_since_source_page_id)
    VALUES (%s, %s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (pipeline_run_id, source_url) DO NOTHING
"""


def _page_row(row: SourcePageRow) -> tuple:
    return (
        row.source_url,
        row.jurisdiction_ocdid,
        row.pipeline_run_id,
        row.changeset_id,
        row.organization_ids,
        row.page_hash,
        row.prompt_hash,
        row.cache_path,
        row.anchor_text,
        row.is_relevant,
        row.relevant_urls,
        row.heuristics_failures,
        row.unchanged_since_source_page_id,
    )


_ORGANIZATIONS_READ = """
    SELECT organization_id::text FROM source_records WHERE changeset_id = %(changeset_id)s
    UNION
    SELECT unnest(organization_ids)::text FROM source_pages WHERE changeset_id = %(changeset_id)s
"""


async def organizations_read_by_changeset(cur, changeset_id: str) -> list[str]:
    """Which bodies this changeset read a page for: any a record names, and any a page row
    names, so a page that listed nobody still counts. The same rule the fold's `reads_of`
    uses, so the issue check sees every read that publishing would act on."""
    await cur.execute(_ORGANIZATIONS_READ, {"changeset_id": changeset_id})
    return [row[0] for row in await cur.fetchall()]


async def published_source_pages(jurisdiction_ocdid: str) -> list[PublishedSourcePage]:
    """Every url's latest reusable row, with the live records its changeset holds for it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            _PUBLISHED_SOURCE_PAGES,
            {"jurisdiction_ocdid": jurisdiction_ocdid, "entity_type": EntityType.SOURCE_PAGE.value},
        )
        pages = await cur.fetchall()
        if not pages:
            return []
        await cur.execute(
            _PUBLISHED_RECORDS,
            {
                "changeset_ids": sorted({page[7] for page in pages}),
                "entity_type": EntityType.SOURCE_RECORD.value,
            },
        )
        records = await cur.fetchall()

    records_by_page: dict[tuple[str, str], list[PersonSourceRecord]] = {}
    for row in records:
        records_by_page.setdefault((row[0], row[1]), []).append(_published_record(row))
    return [
        PublishedSourcePage(
            source_url=page[0],
            read_source_page_id=page[1],
            page_hash=page[2],
            prompt_hash=page[3],
            is_relevant=page[4],
            organization_ids=page[5],
            relevant_urls=page[6],
            known_records=records_by_page.get((page[7], page[0]), []),
        )
        for page in pages
    ]


def _published_record(row: tuple) -> PersonSourceRecord:
    return PersonSourceRecord(
        source_url=row[1],
        name=row[2],
        label=row[3],
        phone=row[4],
        email=row[5],
        url=row[6],
        start_date=row[7],
        end_date=row[8],
        image=row[9],
        cdn_image=row[10],
        other_names=row[11] or [],
        organization_id=row[12],
    )


async def insert_source_pages(rows: list[SourcePageRow]) -> int:
    """A retried submit writes nothing twice: one row per page per run."""
    if not rows:
        return 0
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(_INSERT_PAGE, [_page_row(row) for row in rows])
    return len(rows)
