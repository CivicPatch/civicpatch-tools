"""The projection diff for every jurisdiction with a roster: stored rows against what the
facts derive.

Read-only: nothing is written. The step 8 dry run, and the proof of a backfill. Run in the
app container so it reads the same database the app does:

    docker exec -w /app civicpatch-org python src/scripts/projection_diff.py
    docker exec -w /app civicpatch-org python src/scripts/projection_diff.py --examples 5

It also answers the two questions §15 wants asked before the dry run is read: which labels are
landing in `unmatched`, and how big a fold's fact load gets.
"""

import argparse
import asyncio
import re
from collections import Counter
from datetime import datetime, timezone

import environment
from core.projection.diff import RosterDiff, on_roster, roster_diff
from core.projection.roster import Roster, derive_roster, with_published_images
from database.database import get_pool
from database.facts import load_facts
from database.projection import jurisdictions_with_a_roster, stored_roster
from database.roles import get_roles
from lib import buckets
from pydantic import BaseModel
from shared.schemas import RoleConfig
from shared.utils.taxonomy import (
    UNMATCHED_ROLE_ID,
    Taxonomy,
    build_taxonomy,
    is_designation,
    lookup_key,
)


class Unmatched(BaseModel, frozen=True):
    """A membership the fold put in `unmatched`, and whether that is a parser bug.

    `known_role` is a role the taxonomy carries, named somewhere inside a label that parsed to
    none. Those are the bugs; a label naming an office the taxonomy does not carry on purpose
    (Sheriff, District Attorney) belongs in `unmatched` and is not one.
    """

    jurisdiction_ocdid: str
    person_id: str
    label: str
    known_role: str | None = None


class Comparison(BaseModel, frozen=True):
    jurisdiction_ocdid: str
    diff: RosterDiff
    facts_loaded: int
    memberships_derived: int
    unmatched: tuple[Unmatched, ...] = ()


# An alias is words: "Board of Supervisors, 2nd District" has to lose its comma before the
# phrase inside it can be recognised.
_PUNCTUATION = re.compile(r"[^\w\s]")


def known_role_in(label: str, taxonomy: Taxonomy) -> str | None:
    """A role the taxonomy knows, named by some run of words inside this label.

    `resolve_role` has already answered no for the label as a whole, prefixes shed and fuzz
    included, so this looks for an exact alias the parse walked past. Longest run first, since
    "board of supervisors" should answer before "supervisors" if both are aliases.
    """
    words = lookup_key(_PUNCTUATION.sub(" ", label)).split()
    for size in range(len(words), 0, -1):
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start : start + size])
            role = taxonomy.role_aliases.get(phrase)
            if role and not is_designation(phrase, taxonomy):
                return role
    return None


def unmatched_in(
    jurisdiction_ocdid: str, roster: Roster, taxonomy: Taxonomy
) -> list[Unmatched]:
    return [
        Unmatched(
            jurisdiction_ocdid=jurisdiction_ocdid,
            person_id=person.id,
            label=source.note,
            known_role=known_role_in(source.note, taxonomy),
        )
        for person in roster.people
        for membership in person.memberships
        if membership.post.role_id == UNMATCHED_ROLE_ID
        for source in membership.sources
        if source.note
    ]


async def diff_all() -> list[Comparison]:
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
                Comparison(
                    jurisdiction_ocdid=jurisdiction_ocdid,
                    diff=roster_diff(on_roster(stored), on_roster(derived)),
                    facts_loaded=len(facts.records)
                    + len(facts.claims)
                    + len(facts.withdraws),
                    memberships_derived=sum(
                        len(person.memberships) for person in derived.people
                    ),
                    unmatched=tuple(
                        unmatched_in(jurisdiction_ocdid, derived, taxonomy)
                    ),
                )
            )
    return results


def report_diff(results: list[Comparison], examples: int) -> None:
    differing = [comparison for comparison in results if not comparison.diff.empty]
    print(f"jurisdictions compared: {len(results)}, with differences: {len(differing)}")
    print(
        f"people stored but not derived: "
        f"{sum(len(c.diff.only_before) for c in results)}"
    )
    print(
        f"people derived but not stored: {sum(len(c.diff.only_after) for c in results)}"
    )
    print(
        f"memberships only stored: "
        f"{sum(len(c.diff.memberships_only_before) for c in results)}"
    )
    print(
        f"memberships only derived: "
        f"{sum(len(c.diff.memberships_only_after) for c in results)}"
    )
    by_field = Counter(
        difference.field for c in results for difference in c.diff.fields
    )
    print(f"field differences: {dict(by_field) or 'none'}")
    by_membership_field = Counter(
        difference.field for c in results for difference in c.diff.membership_fields
    )
    print(f"membership field differences: {dict(by_membership_field) or 'none'}")

    for comparison in differing[:examples]:
        result = comparison.diff
        print(f"\n{comparison.jurisdiction_ocdid}")
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


def report_unmatched(results: list[Comparison], examples: int) -> None:
    rows = [row for comparison in results for row in comparison.unmatched]
    derived = sum(comparison.memberships_derived for comparison in results)
    share = f"{100 * len(rows) / derived:.1f}%" if derived else "n/a"
    bugs = [row for row in rows if row.known_role]
    print(f"\nunmatched memberships: {len(rows)} of {derived} derived ({share})")
    print(f"  of those, labels naming a role we do track: {len(bugs)}")

    for label, count in Counter(row.label for row in rows).most_common(examples * 5):
        print(f"  {count:5}  {label}")
    for row in bugs[:examples]:
        print(
            f"  BUG {row.jurisdiction_ocdid} {row.person_id}: "
            f"{row.label!r} names {row.known_role!r}"
        )


def report_load(results: list[Comparison]) -> None:
    """§18's measurement gate: one fold's fact load is what the loader has to carry."""
    loads = sorted(
        ((c.facts_loaded, c.jurisdiction_ocdid) for c in results), reverse=True
    )
    total = sum(count for count, _ in loads)
    print(f"\nfacts loaded: {total} over {len(loads)} jurisdictions")
    for count, jurisdiction_ocdid in loads[:5]:
        print(f"  {count:7}  {jurisdiction_ocdid}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--examples",
        type=int,
        default=3,
        help="jurisdictions and rows to print (default: 3)",
    )
    args = parser.parse_args()
    results = asyncio.run(diff_all())
    report_diff(results, args.examples)
    report_unmatched(results, args.examples)
    report_load(results)


if __name__ == "__main__":
    main()
