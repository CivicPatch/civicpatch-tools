"""Reconstruct `source_records` for in-flight reviews from `requests.data_json`.

Plan: `.scratch/2026-08-18-stacked-scrapes-decisions.md`.

    docker exec -i civicpatch-org python - < database_operations/one_offs/02_backfill_source_records.py
    kubectl exec -i -n civicpatch deploy/civicpatch-org -- python - < <same file>

Dry by default. `--apply` writes, `--limit N` stops after N requests.

`data_json` cannot be retired while the review pool lives only there, and with ~600 in flight
the pool will not drain on its own. This gives those requests evidence rows so publish can
read `source_records` instead.

**These are reconstructions, not sightings**, and every row says so. One row per sighting,
like the pipeline emits: labels and urls cycle together so every url is used. That pairing is a
guess — the merge deduped both lists independently — and `_reconstructed_from` is what stops it
reading as fact. Contact fields are lists there and singular here, so the first of each is
taken. The authoritative roster stays in `data_json` and `people`; nothing is migrated out.

Unpublished, undismissed requests only: published ones already have their roster in `people`.
Idempotent — a request that already has any source record is skipped.
"""

import argparse
import asyncio
import sys

sys.path.insert(0, "/app/src")

from database.database import get_pool  # noqa: E402
from database.roles import get_roles  # noqa: E402
from database.source_records import insert_source_records  # noqa: E402
from shared.schemas import RoleConfig  # noqa: E402
from shared.utils.official_fields import office_name_to_labels  # noqa: E402
from shared.utils.taxonomy import build_taxonomy  # noqa: E402

# Written into every row. `source_records` has no update path by design, so provenance that is
# not recorded now can never be added.
ORIGIN_KEY = "_reconstructed_from"
ORIGIN = "requests.data_json"


def _first(person: dict, key: str) -> str | None:
    values = person.get(key) or []
    return values[0] if values else None


def _records_for(person: dict) -> list[dict]:
    """One record per sighting, the shape the pipeline emits: a label and the page it came from.

    Both lists cycle up to the longer, so every url is used and every label is kept. The
    pairing is a guess — the merge deduped labels and urls independently, so which came from
    which is gone — but it is a better one than sending every row to the first url.
    """
    labels = office_name_to_labels((person.get("office") or {}).get("name") or "")
    urls = person.get("source_urls") or []
    if not labels or not urls:
        return []
    return [
        {
            "name": person.get("name"),
            "label": labels[i % len(labels)],
            "phone": _first(person, "phones"),
            "email": _first(person, "emails"),
            "url": _first(person, "urls"),
            "image": person.get("image"),
            "start_date": person.get("start_date"),
            "end_date": person.get("end_date"),
            "source_url": urls[i % len(urls)],
            ORIGIN_KEY: ORIGIN,
        }
        for i in range(max(len(labels), len(urls)))
    ]


async def _requests_to_do(cur) -> list[tuple]:
    await cur.execute(
        """
        SELECT r.id::text, r.jurisdiction_ocdid, r.data_json
        FROM requests r
        WHERE r.data_json IS NOT NULL
          AND r.published_at IS NULL
          AND r.dismissed_at IS NULL
          AND NOT EXISTS (SELECT 1 FROM source_records s WHERE s.request_id = r.id)
        ORDER BY r.created_at
        """
    )
    return list(await cur.fetchall())


async def main(apply: bool, limit: int | None) -> None:
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        todo = await _requests_to_do(cur)
    if limit:
        todo = todo[:limit]

    print(f"{len(todo)} in-flight request(s) with no source records")
    total_records = skipped_people = failed = 0

    for index, (request_id, jurisdiction_ocdid, data_json) in enumerate(todo, 1):
        records_by_person: dict[str, list[dict]] = {}
        for person in data_json or []:
            person_id = person.get("id")
            records = _records_for(person) if person_id else []
            if not records:
                skipped_people += 1
                continue
            records_by_person[person_id] = records

        if not apply:
            total_records += len(records_by_person)
            continue
        try:
            total_records += await insert_source_records(
                request_id, jurisdiction_ocdid, records_by_person, taxonomy
            )
        except Exception as e:
            failed += 1
            print(f"  FAILED {request_id}: {e}")

        if index % 100 == 0:
            print(f"  {index}/{len(todo)} — {total_records} records")

    verb = "wrote" if apply else "would write"
    print(f"{verb} {total_records} row(s); {skipped_people} person(s) skipped; {failed} failed")
    if not apply:
        print("dry run — nothing written. Re-run with --apply.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.limit))
