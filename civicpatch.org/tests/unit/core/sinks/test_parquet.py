"""The published parquet schema. Pure — rows in, bytes out, no storage and no database."""

import io
from datetime import datetime, timezone

import pyarrow.parquet as pq
import pytest

from core.sinks.parquet import SCHEMAS, SchemaMismatch, to_parquet

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _person(**over) -> dict:
    row = {
        "state": "wa",
        "id": "p1",
        "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:wa/place:x/government",
        "name": "Jane Doe",
        "other_names": [],
        "emails": ["jane@x.gov"],
        "phones": [],
        "urls": [],
        "source_urls": [],
        "image": None,
        "cdn_image": None,
        "updated_at": _NOW,
    }
    return {**row, **over}


def _read(blob: bytes):
    return pq.read_table(io.BytesIO(blob))


@pytest.mark.unit
def test_an_all_null_column_keeps_its_declared_type():
    """The trap the declared schema exists for. Inferring types from values would make
    `cdn_image` a null column in a state where nobody has an image and a string column
    everywhere else, so `read_parquet('people/**/*.parquet')` could not unify the partitions —
    surfacing as a consumer bug months after the write that caused it."""
    wyoming = _read(to_parquet("people", [_person(cdn_image=None)]))
    texas = _read(to_parquet("people", [_person(cdn_image="https://cdn/x.jpg")]))

    assert wyoming.schema == texas.schema
    assert str(wyoming.schema.field("cdn_image").type) == "string"


@pytest.mark.unit
def test_lists_survive_as_lists():
    """The whole reason this is not the sheet, which joins them into `"a | b"`."""
    table = _read(to_parquet("people", [_person(emails=["a@x.gov", "b@x.gov"])]))

    assert str(table.schema.field("emails").type) == "list<element: string>"
    assert table.column("emails").to_pylist() == [["a@x.gov", "b@x.gov"]]


@pytest.mark.unit
def test_timestamps_survive_as_timestamps():
    table = _read(to_parquet("people", [_person()]))

    assert table.column("updated_at").to_pylist() == [_NOW]


@pytest.mark.unit
def test_an_empty_table_still_has_the_full_schema():
    """A state with no rows is skipped by the service, but if one is ever written it must not
    be a file with no columns — that is the other way partitions fail to unify."""
    table = _read(to_parquet("people", []))

    assert table.num_rows == 0
    assert table.schema.names == SCHEMAS["people"].names


@pytest.mark.unit
def test_a_column_the_schema_does_not_name_is_refused():
    """So that adding a column to `database/dumps.py` and forgetting it here fails loudly rather
    than dropping it silently from the published data."""
    with pytest.raises(SchemaMismatch):
        to_parquet("people", [_person(secret_internal_column="leaked")])


@pytest.mark.unit
def test_a_column_the_query_stopped_returning_is_refused():
    """The other direction, and the quieter one: a missing key becomes a column of nulls, so a
    column dropped from the query would publish as null for every row rather than fail."""
    row = _person()
    del row["emails"]

    with pytest.raises(SchemaMismatch):
        to_parquet("people", [row])
