"""The roster as parquet, in R2 — the third sink, beside `roster_sheet` and open-data.

The third sink, and the only one that is not for a person reading it. Open-data git is one
readable YAML file per jurisdiction; the entry sheet is a curator matching wording. This is a
corpus somebody opens in DuckDB.

One file per table. It was partitioned by state until 2026-09-04, when the split turned out to
cost more than it saved: 1.5 MB of memberships across thirteen files meant a full scan opened
thirteen footers where one file needs about five requests. `database/parquet_rows` carries the
reasoning and what would justify partitioning again.

Under the CDN bucket rather than a bucket of its own. That is the one already serving public
objects — `publish.py` copies a published image into it — so a dump needs no new credential
scope, which `lib/buckets.py` warns is the thing that silently 403s when it is missed.
"""

import asyncio
import datetime
import json
import logging

import database.parquet_rows as parquet_rows_db
import lib.buckets as buckets
import lib.storage as storage
from core.sinks.parquet import duckdb_columns, to_parquet

logger = logging.getLogger(__name__)

_PREFIX = "parquet"
_CONTENT_TYPE = "application/vnd.apache.parquet"

# HTTP has no directory listing, so a browser cannot discover `state=*/data.parquet` by globbing
# — the viewer has to be handed the file list. That is what this is for, and it carries the row
# counts and column types too so the page does not read every partition's footer to show a
# schema. Paths are relative to `_PREFIX`, which is the viewer's base URL.
MANIFEST_KEY = f"{_PREFIX}/manifest.json"


def table_key(table: str) -> str:
    return f"{_PREFIX}/{table}/data.parquet"


async def _put(key: str, body: bytes) -> None:
    # boto3 is synchronous and would block the event loop, as in `sinks.sheet`.
    await asyncio.to_thread(
        storage.upload_bytes_to_storage, buckets.CDN, key, body, _CONTENT_TYPE
    )


def _relative(key: str) -> str:
    return key[len(_PREFIX) + 1 :]


async def sync_all() -> dict[str, dict]:
    """Every table, then the manifest that names them.

    The manifest is written last on purpose: it names files, so publishing it before they exist
    would point a reader at a 404. Written whole every run rather than patched, because a table
    that drops to zero rows has to leave the list.
    """
    tables: dict[str, dict] = {}
    for table in parquet_rows_db.TABLES:
        rows = await parquet_rows_db.rows(table)
        if not rows:
            continue
        key = table_key(table)
        await _put(key, to_parquet(table, rows))
        tables[table] = {
            "name": table,
            "rows": len(rows),
            "file": _relative(key),
            "columns": duckdb_columns(table),
        }

    manifest = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tables": sorted(tables.values(), key=lambda t: t["name"]),
    }
    await asyncio.to_thread(
        storage.upload_bytes_to_storage,
        buckets.CDN,
        MANIFEST_KEY,
        json.dumps(manifest, indent=2).encode(),
        "application/json",
    )
    logger.info("Parquet: %d tables, %d rows", len(tables), sum(t["rows"] for t in tables.values()))
    return tables
