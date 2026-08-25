"""Derive organizations, posts and memberships for people published before they existed.

    docker exec -i civicpatch-org python - < database_operations/one_offs/02_backfill_posts_memberships.py
    kubectl exec -i -n civicpatch deploy/civicpatch-org -- python - < <same file>

Dry by default. `--apply` writes, `--limit N` stops after N jurisdictions.

Jurisdictions that already have memberships are skipped: `memberships.upsert` closes a
person's other open membership and advances `last_seen_at` on a match, and neither is
recoverable from a `created_at` window. Re-deriving those is a different job.
"""

import argparse
import asyncio
import sys

sys.path.insert(0, "/app/src")

from core.post_derivation import derived_posts  # noqa: E402
from database import divisions, memberships, organizations, posts  # noqa: E402
from database.database import get_pool  # noqa: E402
from database.roles import get_roles  # noqa: E402
from shared.schemas import Official, RoleConfig  # noqa: E402
from shared.utils.taxonomy import build_taxonomy  # noqa: E402

INACTIVE = "inactive"


async def _jurisdictions_to_do(cur) -> list[str]:
    await cur.execute(
        """
        SELECT DISTINCT p.jurisdiction_ocdid
        FROM people p
        WHERE NOT EXISTS (
            SELECT 1 FROM memberships m
            JOIN posts po ON po.id = m.post_id
            WHERE po.jurisdiction_ocdid = p.jurisdiction_ocdid
        )
        ORDER BY 1
        """
    )
    return [row[0] for row in await cur.fetchall()]


async def _people(cur, jurisdiction_ocdid: str) -> list[tuple]:
    await cur.execute(
        """
        SELECT id::text, data, status, updated_at FROM people
        WHERE jurisdiction_ocdid = %s
        """,
        (jurisdiction_ocdid,),
    )
    return await cur.fetchall()


def _officials(rows: list[tuple], jurisdiction_ocdid: str) -> list[Official]:
    """`id` is the stored person id, which is what `DerivedMember.person_id` carries through."""
    built = []
    for person_id, data, _status, _updated_at in rows:
        built.append(
            Official(
                **{**data, "id": person_id, "jurisdiction_ocdid": jurisdiction_ocdid}
            )
        )
    return built


async def _backfill_one(
    cur, jurisdiction_ocdid: str, taxonomy, roles
) -> tuple[int, int]:
    rows = await _people(cur, jurisdiction_ocdid)
    if not rows:
        return 0, 0

    seen_at = {person_id: updated_at for person_id, _d, _s, updated_at in rows}
    inactive = {person_id for person_id, _d, status, _u in rows if status == INACTIVE}

    specs = derived_posts(_officials(rows, jurisdiction_ocdid), taxonomy, roles)
    organization_id = await organizations.find_or_create(cur, jurisdiction_ocdid)

    membership_count = 0
    for spec in specs:
        await divisions.find_or_create(cur, spec.division_ocdid, jurisdiction_ocdid)
        post_id = await posts.find_or_create(
            cur,
            jurisdiction_ocdid,
            organization_id,
            spec.role_id,
            spec.division_ocdid,
            headcount=spec.headcount,
        )
        for member in spec.members:
            membership_id = await memberships.upsert(
                cur,
                member.person_id,
                post_id,
                organization_id,
                seen_at[member.person_id],
                designations=member.designations,
                unmatched_text=member.unmatched_text,
                source_labels=member.source_labels,
                role_ids=member.role_ids,
                label=member.label,
            )
            membership_count += 1
            if member.person_id in inactive:
                # The latest roster stopped naming them, which is what a closed membership
                # says. `updated_at` is the only date we hold for when that was.
                await cur.execute(
                    "UPDATE memberships SET closed_at = %s WHERE id::text = %s",
                    (seen_at[member.person_id], membership_id),
                )

    return len(specs), membership_count


async def main(apply: bool, limit: int | None) -> None:
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        todo = await _jurisdictions_to_do(cur)
    if limit:
        todo = todo[:limit]

    print(f"{len(todo)} jurisdiction(s) with people and no memberships")
    total_posts = total_memberships = failed = 0

    for index, jurisdiction_ocdid in enumerate(todo, 1):
        # One transaction each: 3,432 of them, and a bad row must not undo the rest.
        try:
            async with pool.connection() as conn, conn.cursor() as cur:
                post_count, membership_count = await _backfill_one(
                    cur, jurisdiction_ocdid, taxonomy, roles
                )
                if apply:
                    await conn.commit()
                else:
                    await conn.rollback()
            total_posts += post_count
            total_memberships += membership_count
        except Exception as e:
            failed += 1
            print(f"  FAILED {jurisdiction_ocdid}: {e}")

        if index % 250 == 0:
            print(
                f"  {index}/{len(todo)} — {total_posts} posts, {total_memberships} memberships"
            )

    verb = "wrote" if apply else "would write"
    print(
        f"{verb} {total_posts} posts and {total_memberships} memberships; {failed} failed"
    )
    if not apply:
        print("dry run — nothing committed. Re-run with --apply.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.limit))
