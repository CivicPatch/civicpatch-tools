"""The published schema for each dumped table, and rows turned into parquet bytes.

**The schema is declared, never inferred.** `pa.Table.from_pylist(rows)` reads types off the
values, which is fine until a column happens to be null for every row in one partition — then
Wyoming's `cdn_image` is `null` type while Texas's is `string`, and
`read_parquet('people/**/*.parquet')` fails to unify them. The partitions are written months
apart by different runs, so this would surface as a consumer bug long after the write that
caused it. Declaring the schema makes every partition of a table identical by construction.

It is also the same contract `database/dumps.py` states in its column lists, carried one step
further: that file decides *which* columns are published, this one decides what they are.

Pure: rows in, bytes out. No storage, no database.
"""

import io

import pyarrow as pa
import pyarrow.parquet as pq

_TIMESTAMP = pa.timestamp("us", tz="UTC")
_STRINGS = pa.list_(pa.string())

SCHEMAS: dict[str, pa.Schema] = {
    "people": pa.schema(
        [
            ("state", pa.string()),
            ("id", pa.string()),
            ("jurisdiction_ocdid", pa.string()),
            ("name", pa.string()),
            ("other_names", _STRINGS),
            ("emails", _STRINGS),
            ("phones", _STRINGS),
            ("urls", _STRINGS),
            ("source_urls", _STRINGS),
            ("image", pa.string()),
            ("cdn_image", pa.string()),
            ("updated_at", _TIMESTAMP),
        ]
    ),
    "memberships": pa.schema(
        [
            ("state", pa.string()),
            ("id", pa.string()),
            ("person_id", pa.string()),
            ("post_id", pa.string()),
            ("organization_id", pa.string()),
            ("jurisdiction_ocdid", pa.string()),
            ("label", pa.string()),
            # Text, not date: these are as the source wrote them, and a source writes "2024"
            # or "Jan 2024" as often as a real date. Parsing here would invent precision.
            ("start_date", pa.string()),
            ("end_date", pa.string()),
            ("first_seen_at", _TIMESTAMP),
            ("last_seen_at", _TIMESTAMP),
            ("closed_at", _TIMESTAMP),
            ("created_at", _TIMESTAMP),
            ("designations", _STRINGS),
            ("source_labels", _STRINGS),
            ("is_open", pa.bool_()),
        ]
    ),
    "posts": pa.schema(
        [
            ("state", pa.string()),
            ("id", pa.string()),
            ("jurisdiction_ocdid", pa.string()),
            ("organization_id", pa.string()),
            ("role_id", pa.string()),
            ("division_ocdid", pa.string()),
            ("created_at", _TIMESTAMP),
        ]
    ),
    "organizations": pa.schema(
        [
            ("state", pa.string()),
            ("id", pa.string()),
            ("jurisdiction_ocdid", pa.string()),
            ("name", pa.string()),
            ("sort_order", pa.int32()),
            ("created_at", _TIMESTAMP),
        ]
    ),
    "divisions": pa.schema(
        [
            ("state", pa.string()),
            ("ocdid", pa.string()),
            ("jurisdiction_ocdid", pa.string()),
            ("created_at", _TIMESTAMP),
        ]
    ),
    "jurisdictions": pa.schema(
        [
            ("state", pa.string()),
            ("jurisdiction_ocdid", pa.string()),
            ("level", pa.string()),
            ("status", pa.string()),
            ("name", pa.string()),
            ("parent_ocdids", _STRINGS),
            ("scraped_at", _TIMESTAMP),
            ("updated_at", _TIMESTAMP),
        ]
    ),
    "roles": pa.schema(
        [
            ("id", pa.string()),
            ("label", pa.string()),
            ("status", pa.string()),
            ("is_unique", pa.bool_()),
            ("priority", pa.int32()),
            ("created_at", _TIMESTAMP),
        ]
    ),
}


# Parquet carries pyarrow's names; the viewer is a DuckDB console, so the manifest publishes
# the names somebody writing SQL against it will actually see.
#
# Matched on the type, not on `str(type)`: pyarrow spells a list field `list<item: string>` in a
# schema and `list<element: string>` in a table read back from a file, so string comparison is
# right until the day it silently is not.
def _duckdb_name(dtype: pa.DataType) -> str:
    if pa.types.is_list(dtype):
        return "VARCHAR[]"
    if pa.types.is_timestamp(dtype):
        return "TIMESTAMP WITH TIME ZONE"
    if pa.types.is_boolean(dtype):
        return "BOOLEAN"
    if pa.types.is_int32(dtype):
        return "INTEGER"
    if pa.types.is_string(dtype):
        return "VARCHAR"
    return str(dtype)


def duckdb_columns(table: str) -> list[dict[str, str]]:
    """This table's published columns, named as DuckDB will report them."""
    return [
        {"name": field.name, "type": _duckdb_name(field.type)}
        for field in SCHEMAS[table]
    ]


class SchemaMismatch(ValueError):
    """The query and the published schema disagree about what this table's columns are."""


def to_parquet(table: str, rows: list[dict]) -> bytes:
    """Rows as a parquet file, under this table's declared schema.

    Checked both ways first, because `pa.Table.from_pylist` is silent in both directions: an
    extra key is dropped, and a missing one becomes a column of nulls. Either would publish
    quietly wrong data — a column added to `database/dumps.py` and forgotten here would never
    appear, and one removed there would appear as null for every row.
    """
    schema = SCHEMAS[table]
    if rows:
        declared, present = set(schema.names), set(rows[0])
        if declared != present:
            raise SchemaMismatch(
                f"{table}: query has {sorted(present - declared)}, "
                f"schema has {sorted(declared - present)}"
            )
    arrow = pa.Table.from_pylist(rows, schema=schema)
    buffer = io.BytesIO()
    # zstd over snappy: better ratio at a speed nothing here is bound by, and every reader
    # that can open a parquet file written this decade supports it.
    pq.write_table(arrow, buffer, compression="zstd")
    return buffer.getvalue()
