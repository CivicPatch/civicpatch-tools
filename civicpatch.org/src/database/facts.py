"""Loads one jurisdiction's facts for the fold.

The only module that knows how facts are stored. It filters (published changesets, the as-of
cutoff, withdraws never cut) so `core/projection/` can trust what it is handed, and it adapts
today's schema to the shape the resolvers will keep: the two adapters below are deleted by a
named step, and nothing in `core/` has to know they existed. Withdraws are rows (214).
"""

from datetime import datetime

from core.changeset_lifecycle import PARTIAL_KINDS
from core.people_edits import POSTS_FIELD
from core.projection.facts import Claim, ClaimKind, Facts, PostKey, SourceRecord
from core.projection.person_ids import PERSON_ID
from database.changeset_predicates import OPEN_REVIEW_EDIT
from database.database import get_pool
from shared.utils.statuses import ChangesetKind

# Only a published changeset's facts derive (R3), plus the one changeset a caller asks to see
# as though it had published, which is what a proposed roster is. `including` is NULL for the
# live roster, and `id = NULL` is never true, so that caller pays nothing for the clause.
#
# The scrape's open review edit comes along, because publishing the scrape publishes it (9f).
_INCLUDED = f"""(
    changesets.id = %(including)s
    OR (changesets.parent_changeset_id = %(including)s AND {OPEN_REVIEW_EDIT})
)"""

#
# `claims.changeset_id` is still nullable today — a direct field assert or an edit made
# outside review has none — and those claims are live, so they must not be dropped by the
# join. Step 16 makes the column NOT NULL and this becomes a plain inner join.
_PUBLISHED_OR_UNATTRIBUTED = f"""
    LEFT JOIN changesets ON changesets.id = claims.changeset_id
    WHERE (
        (claims.changeset_id IS NULL AND claims.created_at <= %(as_of)s)
        OR changesets.published_at <= %(as_of)s
        OR {_INCLUDED}
    )
"""

_RECORDS = f"""
    SELECT source_records.id::text, source_records.changeset_id::text,
           source_records.created_at, source_records.person_id::text,
           source_records.organization_id::text, source_records.name, source_records.label,
           source_records.source_url, source_records.other_names, source_records.url,
           source_records.phone, source_records.email, source_records.image,
           source_records.cdn_image, source_records.start_date, source_records.end_date,
           changesets.kind
    FROM source_records
    JOIN changesets ON changesets.id = source_records.changeset_id
    WHERE source_records.jurisdiction_ocdid = %(jurisdiction_ocdid)s
      AND (changesets.published_at <= %(as_of)s OR {_INCLUDED})
"""

# A `posts` claim's value is a post's id, and the fold works in post keys, so the join is the
# translation. A claim naming a post that no longer exists keeps its id and matches none of the
# fold's posts, which is the same as placing nobody.
#
# By person id for people a record names, and by changeset for a hand-add, whom no record names.
_PERSON_CLAIMS = f"""
    SELECT claims.id::text, claims.changeset_id::text, claims.created_at,
           claims.entity_type, claims.entity_id::text, claims.field_path,
           claims.kind, claims.value,
           posts.organization_id::text, posts.role_id, posts.division_ocdid
    FROM claims
    LEFT JOIN posts ON claims.field_path = '{POSTS_FIELD}'
                   AND posts.id::text = claims.value #>> '{{}}'
    {_PUBLISHED_OR_UNATTRIBUTED}
      AND claims.entity_type = 'person'
      AND (claims.entity_id::text = ANY(%(person_ids)s)
           OR changesets.jurisdiction_ocdid = %(jurisdiction_ocdid)s)
"""

# A split: a record re-linked to another person (§8). Its value names the person, who may be
# known to no record, so these load before the person claims.
_RECORD_CLAIMS = f"""
    SELECT claims.id::text, claims.changeset_id::text, claims.created_at,
           claims.entity_type, claims.entity_id::text, claims.field_path,
           claims.kind, claims.value, NULL, NULL, NULL
    FROM claims
    {_PUBLISHED_OR_UNATTRIBUTED}
      AND claims.entity_type = 'source_record'
      AND claims.entity_id::text = ANY(%(record_ids)s)
"""

# By the jurisdiction the claim was made in, not by the membership's id: the id is a hash of
# `(person, post)` that no query can join on. The fold matches them to its own posts, so a
# claim about somebody else's membership is inert — `changeset_id IS NULL` is the pre-review
# claims, which name no jurisdiction until step 16.
_MEMBERSHIP_CLAIMS = f"""
    SELECT claims.id::text, claims.changeset_id::text, claims.created_at,
           claims.entity_type, claims.entity_id::text, claims.field_path,
           claims.kind, claims.value, NULL, NULL, NULL
    FROM claims
    {_PUBLISHED_OR_UNATTRIBUTED}
      AND claims.entity_type = 'membership'
      AND (changesets.jurisdiction_ocdid = %(jurisdiction_ocdid)s
           OR claims.changeset_id IS NULL)
"""

# Every published withdraw that can affect this jurisdiction. Scoping by the changeset's own
# jurisdiction is safe because only `services/rollback.py` files a withdraw under one, and it
# takes that jurisdiction from the target's own `people` row, so the two always agree. Every
# other withdrawal (a cleared label, a taken-back rejection) leaves `changeset_id` NULL and is
# loaded unconditionally. Never cut by date: a rolled-back edit is gone from every as-of.
_WITHDRAWS = f"""
    SELECT claims.id::text, claims.changeset_id::text, claims.created_at,
           claims.entity_type, claims.entity_id::text, claims.field_path,
           claims.kind, claims.value, NULL, NULL, NULL
    FROM claims
    LEFT JOIN changesets ON changesets.id = claims.changeset_id
    WHERE claims.kind = '{ClaimKind.WITHDRAW.value}'
      AND (
          claims.changeset_id IS NULL
          OR (
              (changesets.published_at IS NOT NULL OR {_INCLUDED})
              AND (changesets.jurisdiction_ocdid = %(jurisdiction_ocdid)s
                   OR changesets.jurisdiction_ocdid IS NULL)
          )
      )
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
        is_partial=ChangesetKind(row[16]) in PARTIAL_KINDS,
    )


def _claim(row: tuple) -> Claim:
    """A claim as the fold reads one. A `posts` claim stores the post's id and the fold works
    in keys, so the join resolves one onto the claim."""
    return Claim(
        id=row[0],
        changeset_id=row[1],
        created_at=row[2],
        entity_type=row[3],
        entity_id=row[4],
        field_path=row[5],
        kind=row[6],
        value=row[7],
        post=PostKey(organization_id=row[8], role_id=row[9], division_ocdid=row[10])
        if row[8]
        else None,
    )


async def load_facts(
    cur, jurisdiction_ocdid: str, as_of: datetime, including: str | None = None
) -> Facts:
    """Every live fact this jurisdiction's roster derives from, as at `as_of`.

    `including` names one unpublished changeset to read as though it had published, which is
    what makes a proposed roster `derive(published facts + this changeset)` (R3), its open
    review edit included. Nothing is written either way.

    Claims about records, people and memberships; post, organization and taxonomy claims join as their
    write paths move onto the model (steps 10, 11 and 18).

    `reads` stays empty until `source_pages` exists: `core.projection.reads.reads_of` infers a
    read from any live record naming the organization, which is today's rule, and page rows
    will union with that rather than replace it.
    """
    scope = {
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "as_of": as_of,
        "including": including,
    }
    await cur.execute(_RECORDS, scope)
    rows = await cur.fetchall()
    records = tuple(_record(row) for row in rows)

    claims: tuple[Claim, ...] = ()
    if records:
        await cur.execute(_RECORD_CLAIMS, {**scope, "record_ids": [record.id for record in records]})
        claims = tuple(_claim(row) for row in await cur.fetchall())

    person_ids = sorted(
        {record.person_id for record in records}
        | {str(claim.value) for claim in claims if claim.field_path == PERSON_ID}
    )
    await cur.execute(_PERSON_CLAIMS, {**scope, "person_ids": person_ids})
    claims += tuple(_claim(row) for row in await cur.fetchall())
    await cur.execute(_MEMBERSHIP_CLAIMS, scope)
    claims += tuple(_claim(row) for row in await cur.fetchall())

    await cur.execute(_WITHDRAWS, scope)
    withdraws = tuple(_claim(row) for row in await cur.fetchall())

    return Facts(
        records=records,
        claims=claims,
        withdraws=withdraws,
        reads=(),
    )


async def load_facts_for(
    jurisdiction_ocdid: str, as_of: datetime, including: str | None = None
) -> Facts:
    """`load_facts` on its own connection, for callers outside a transaction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await load_facts(cur, jurisdiction_ocdid, as_of, including)
