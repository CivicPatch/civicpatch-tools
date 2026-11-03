"""Rebuild every jurisdiction with an open membership on a retired role, then delete the posts
the rebuild left empty. A one-off for plan 2026-10-30-plan-roles-from-config.md, step 3a: the
chair roles became member roles, but `rebuild_from_facts` runs only on publish, so 93 places
still held their chairs on the old posts.

Without --apply it writes nothing and prints, per jurisdiction, what the rebuild would change:
chairs moving off a retired post, and anything else, which has to be explained before --apply.
Run in the app container:

    docker exec -w /app civicpatch-org python src/scripts/rebuild_retired_role_posts.py
    docker exec -w /app civicpatch-org python src/scripts/rebuild_retired_role_posts.py --apply
"""

import argparse
import asyncio

from pydantic import BaseModel

from core.projection.diff import on_roster, roster_diff
from core.projection.roster import Roster
from database.database import get_pool
from database.projection import delete_empty_posts, derived_roster, rebuild_from_facts, stored_roster
from shared.utils.taxonomy import MEMBER_ROLE_ID

RETIRED_ROLE_IDS = ["select-board-chair", "select-board-vice-chair"]

_JURISDICTIONS_ON_RETIRED_ROLES = """
SELECT DISTINCT posts.jurisdiction_ocdid
FROM posts
JOIN memberships ON memberships.post_id = posts.id
WHERE posts.role_id = ANY(%s) AND memberships.closed_at IS NULL
ORDER BY posts.jurisdiction_ocdid
"""


class RebuildPreview(BaseModel):
    chairs_moved: int
    # Every change that is not a chair leaving a retired post for a member post, one line each.
    other_changes: list[str]


def rebuild_preview(stored: Roster, derived: Roster) -> RebuildPreview:
    diff = roster_diff(stored, derived)
    role_of = {
        (person.id, membership.post.post_id): membership.post.role_id
        for roster in (stored, derived)
        for person in roster.people
        for membership in person.memberships
    }
    left_retired = {key for key in diff.memberships_only_before if role_of[key] in RETIRED_ROLE_IDS}
    moved_people = {person_id for person_id, _ in left_retired}
    other = [f"person left the roster: {person_id}" for person_id in diff.only_before]
    other += [f"person joined the roster: {person_id}" for person_id in diff.only_after]
    other += [f"{change.person_id} {change.field}: {change.before!r} -> {change.after!r}" for change in diff.fields]
    other += [
        f"{person_id} left a {role_of[(person_id, post_id)]} post"
        for person_id, post_id in diff.memberships_only_before
        if (person_id, post_id) not in left_retired
    ]
    other += [
        f"{person_id} joined a {role_of[(person_id, post_id)]} post"
        for person_id, post_id in diff.memberships_only_after
        if not (person_id in moved_people and role_of[(person_id, post_id)] == MEMBER_ROLE_ID)
    ]
    other += [
        f"{change.person_id} membership {change.field}: {change.before!r} -> {change.after!r}"
        for change in diff.membership_fields
    ]
    return RebuildPreview(chairs_moved=len(left_retired), other_changes=other)


async def jurisdictions_on_retired_roles() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(_JURISDICTIONS_ON_RETIRED_ROLES, (RETIRED_ROLE_IDS,))
        return [row[0] for row in await cur.fetchall()]


async def preview(jurisdiction_ocdid: str) -> RebuildPreview:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await conn.set_read_only(True)
        stored = await stored_roster(cur, jurisdiction_ocdid)
        derived = await derived_roster(cur, jurisdiction_ocdid)
    return rebuild_preview(on_roster(stored), on_roster(derived))


async def rebuild_and_delete(jurisdiction_ocdids: list[str]) -> int:
    """Each rebuild commits on its own, so one failure leaves the others done. Returns the
    number of posts deleted."""
    pool = await get_pool()
    for jurisdiction_ocdid in jurisdiction_ocdids:
        async with pool.connection() as conn, conn.cursor() as cur:
            people = await rebuild_from_facts(cur, jurisdiction_ocdid)
            await conn.commit()
            print(f"rebuilt {jurisdiction_ocdid}: {people} people")
    async with pool.connection() as conn, conn.cursor() as cur:
        deleted = await delete_empty_posts(cur, RETIRED_ROLE_IDS, jurisdiction_ocdids)
        await conn.commit()
        return deleted


async def print_previews(jurisdiction_ocdids: list[str]) -> None:
    with_other_changes = 0
    for jurisdiction_ocdid in jurisdiction_ocdids:
        result = await preview(jurisdiction_ocdid)
        print(f"{jurisdiction_ocdid}: {result.chairs_moved} chair(s) move to a member post")
        for line in result.other_changes:
            print(f"    also: {line}")
        if result.other_changes:
            with_other_changes += 1
    print(f"{with_other_changes} of {len(jurisdiction_ocdids)} jurisdictions change more than their chairs")


async def main(apply: bool) -> None:
    jurisdiction_ocdids = await jurisdictions_on_retired_roles()
    print(f"{len(jurisdiction_ocdids)} jurisdictions with open memberships on {RETIRED_ROLE_IDS}")
    if not apply:
        await print_previews(jurisdiction_ocdids)
        print("dry run: nothing written. Pass --apply to rebuild and delete the empty posts.")
        return
    deleted = await rebuild_and_delete(jurisdiction_ocdids)
    print(f"deleted {deleted} empty posts on retired roles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="rebuild and delete; without it, only list")
    asyncio.run(main(parser.parse_args().apply))
