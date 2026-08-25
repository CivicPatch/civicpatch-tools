"""Empty the unreviewed scrape pool, and delete every reconstructed source_record.

    kubectl exec -i -n civicpatch deploy/civicpatch-org -- python - < <this file>

Dry by default. `--apply` writes.

Every `source_records` row in production is a reconstruction: the 2026-08-18 backfill split
`data_json` rosters back into per-label sightings, and no scrape has run since to produce a
real one. Their label/url pairing is invented — the merge deduped both lists independently —
so they cannot answer "what did the source say", which is the only reason records exist.

Both go, and they go together. Discarding the pool alone leaves reconstructions behind on
requests published or dismissed since the backfill (12 of 51 on dev), which would mean every
future reader having to tell them apart. Deleting them outright means `source_records` holds
sightings and nothing else.

Nothing real is lost: they were derived from `data_json`, which still holds the roster.

Published and already-dismissed requests keep their genuine records.
"""

import argparse
import asyncio
import sys

sys.path.insert(0, "/app/src")

from database.database import get_pool  # noqa: E402

# Distinct from `superseded` (a newer scrape replaced it, unread) and `unchanged` (the roster
# matched what we already hold). This one is "nobody read it and nobody will".
DISCARDED = "discarded"

_POOL = """
    SELECT id FROM requests
    WHERE data_json IS NOT NULL AND published_at IS NULL AND dismissed_at IS NULL
"""

_RECONSTRUCTED = """raw @> '[{"_reconstructed_from": "requests.data_json"}]'"""


async def main(apply: bool) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT (SELECT count(*) FROM requests WHERE id IN ({_POOL})),
                   (SELECT count(DISTINCT jurisdiction_ocdid) FROM requests
                     WHERE id IN ({_POOL})),
                   (SELECT count(*) FROM source_records WHERE {_RECONSTRUCTED}),
                   (SELECT count(*) FROM source_records WHERE NOT {_RECONSTRUCTED})
            """
        )
        requests, jurisdictions, reconstructed, genuine = (await cur.fetchone()) or (0,) * 4

        print(f"{requests} unreviewed requests across {jurisdictions} jurisdictions")
        print(f"{reconstructed} reconstructed source_records would be deleted")
        print(f"{genuine} genuine source_records would be kept")
        if not apply:
            print("\nDry run. Re-run with --apply to write.")
            return

        await cur.execute(f"DELETE FROM source_records WHERE {_RECONSTRUCTED}")
        deleted = cur.rowcount
        await cur.execute(
            f"""
            UPDATE requests SET dismissed_at = now(), dismissed_reason = '{DISCARDED}'
            WHERE id IN ({_POOL})
            """
        )
        dismissed = cur.rowcount
        await conn.commit()
        print(f"Deleted {deleted} reconstructions, dismissed {dismissed} requests.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
