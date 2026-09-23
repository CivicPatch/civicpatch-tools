"""The projection diff for every jurisdiction with a roster: stored rows against what the
facts derive.

Read-only: nothing is written. The step 8 dry run, and the proof of a backfill. Run in the
app container so it reads the same database the app does:

    docker exec -w /app civicpatch-org python src/scripts/projection_diff.py
    docker exec -w /app civicpatch-org python src/scripts/projection_diff.py --examples 5
"""

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone

from shared.schemas import RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.projection.diff import RosterDiff, on_roster, roster_diff
import environment
from core.projection.roster import derive_roster, with_published_images
from database.database import get_pool
from database.facts import load_facts
from database.projection import jurisdictions_with_a_roster, stored_roster
from database.roles import get_roles
from lib import buckets


async def diff_all() -> list[tuple[str, RosterDiff]]:
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))
    as_of = datetime.now(timezone.utc)
    friendly_host = environment.get_env_vars()["FRIENDLY_STORAGE_HOST"]
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await conn.set_read_only(True)
        results = []
        for jurisdiction_ocdid in await jurisdictions_with_a_roster(cur):
            facts = await load_facts(cur, jurisdiction_ocdid, as_of)
            derived = with_published_images(
                derive_roster(facts, jurisdiction_ocdid, taxonomy),
                buckets.ARTIFACTS,
                friendly_host,
            )
            stored = await stored_roster(cur, jurisdiction_ocdid)
            results.append(
                (jurisdiction_ocdid, roster_diff(on_roster(stored), on_roster(derived)))
            )
    return results


def report(results: list[tuple[str, RosterDiff]], examples: int) -> None:
    differing = [(ocdid, diff) for ocdid, diff in results if not diff.empty]
    print(f"jurisdictions compared: {len(results)}, with differences: {len(differing)}")
    print(
        f"people stored but not derived: "
        f"{sum(len(r.only_before) for _, r in results)}"
    )
    print(f"people derived but not stored: {sum(len(r.only_after) for _, r in results)}")
    print(
        f"memberships only stored: "
        f"{sum(len(r.memberships_only_before) for _, r in results)}"
    )
    print(
        f"memberships only derived: "
        f"{sum(len(r.memberships_only_after) for _, r in results)}"
    )
    by_field = Counter(difference.field for _, r in results for difference in r.fields)
    print(f"field differences: {dict(by_field) or 'none'}")
    by_membership_field = Counter(
        difference.field for _, r in results for difference in r.membership_fields
    )
    print(f"membership field differences: {dict(by_membership_field) or 'none'}")

    for jurisdiction_ocdid, result in differing[:examples]:
        print(f"\n{jurisdiction_ocdid}")
        for person_id in result.only_before[:examples]:
            print(f"  only stored:  {person_id}")
        for person_id in result.only_after[:examples]:
            print(f"  only derived: {person_id}")
        for person_id, post_id in result.memberships_only_before[:examples]:
            print(f"  membership only stored:  {person_id} {post_id}")
        for person_id, post_id in result.memberships_only_after[:examples]:
            print(f"  membership only derived: {person_id} {post_id}")
        for difference in result.fields[:examples]:
            print(
                f"  {difference.person_id} {difference.field}: "
                f"stored={difference.before!r} derived={difference.after!r}"
            )
        for difference in result.membership_fields[:examples]:
            print(
                f"  {difference.person_id} {difference.post_id} {difference.field}: "
                f"stored={difference.before!r} derived={difference.after!r}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--examples", type=int, default=3, help="jurisdictions and rows to print (default: 3)"
    )
    args = parser.parse_args()
    report(asyncio.run(diff_all()), args.examples)


if __name__ == "__main__":
    main()
