"""The pure pieces of `seed_open_data_subset`: reading the open-data archive, and the per-table
transforms from a published parquet row to an insert-ready one. No DB, no network: those are
exercised by running the script itself (see the module docstring), not by a mock-heavy unit test.
"""

import io
import tarfile

import pytest

from scripts.seed_open_data_subset import (
    NO_LIMIT,
    division_row,
    jurisdiction_files,
    limit_arg,
    membership_row,
    organization_row,
    person_row,
    post_row,
    role_alias_row,
    role_row,
    rows_in_jurisdictions,
    states_arg,
)

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"


def _archive(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        tar.addfile(tarfile.TarInfo("open-data-main/data_source"))
        for path, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(f"open-data-main/{path}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@pytest.mark.unit
def test_jurisdiction_files_strips_the_archive_directory_and_keeps_only_jurisdiction_lists():
    archive = _archive(
        {
            "data_source/wa/local/jurisdictions.yml": "jurisdictions: []\n",
            "data_source/wa/local/other.yml": "ignored\n",
            "README.md": "ignored\n",
        }
    )

    assert jurisdiction_files(archive) == {
        "data_source/wa/local/jurisdictions.yml": "jurisdictions: []\n"
    }


@pytest.mark.unit
def test_role_row_drops_nothing_it_should_not():
    row = role_row(
        {
            "id": "mayor",
            "label": "Mayor",
            "status": "active",
            "is_unique": True,
            "priority": 1,
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    assert set(row) == {"id", "label", "status", "is_unique", "priority", "created_at"}


@pytest.mark.unit
def test_role_alias_row_keeps_the_role_it_names():
    row = role_alias_row(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "role_id": "mayor-pro-tempore",
            "label": "Mayor Pro Tem",
            "status": "active",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    assert row["role_id"] == "mayor-pro-tempore"
    assert set(row) == {"id", "role_id", "label", "status", "created_at"}


@pytest.mark.unit
def test_division_row_drops_the_derived_state_column():
    """`state` is computed by the export for filtering — it is not a real column on
    `divisions`, so the transform must not try to insert it."""
    row = division_row(
        {
            "state": "wa",
            "ocdid": "ocd-division/country:us/state:wa/place:seattle",
            "jurisdiction_ocdid": _OCDID,
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    assert "state" not in row
    assert row["ocdid"] == "ocd-division/country:us/state:wa/place:seattle"


@pytest.mark.unit
def test_organization_row_carries_the_newly_exported_url():
    row = organization_row(
        {
            "state": "wa",
            "id": "11111111-1111-1111-1111-111111111111",
            "jurisdiction_ocdid": _OCDID,
            "name": "Government",
            "sort_order": 0,
            "url": "https://seattle.gov",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    assert "state" not in row
    assert row["url"] == "https://seattle.gov"


@pytest.mark.unit
def test_organization_row_carries_the_default_flag_when_exported():
    row = organization_row(
        {
            "state": "wa",
            "id": "11111111-1111-1111-1111-111111111111",
            "jurisdiction_ocdid": _OCDID,
            "name": "Government",
            "sort_order": 0,
            "url": None,
            "meta_is_default": True,
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    assert row["meta_is_default"] is True


@pytest.mark.unit
def test_post_row_drops_the_derived_state_column():
    row = post_row(
        {
            "state": "wa",
            "id": "22222222-2222-2222-2222-222222222222",
            "jurisdiction_ocdid": _OCDID,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "role_id": "mayor",
            "division_ocdid": "ocd-division/country:us/state:wa/place:seattle",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )

    assert "state" not in row


@pytest.mark.unit
def test_person_row_drops_the_derived_state_column():
    row = person_row(
        {
            "state": "wa",
            "id": "33333333-3333-3333-3333-333333333333",
            "jurisdiction_ocdid": _OCDID,
            "name": "Jane Doe",
            "other_names": [],
            "emails": ["jane@seattle.gov"],
            "phones": [],
            "urls": [],
            "source_urls": [],
            "image": None,
            "cdn_image": None,
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )

    assert "state" not in row
    assert row["emails"] == ["jane@seattle.gov"]


@pytest.mark.unit
def test_membership_row_drops_derived_and_unexported_columns():
    """`state` and `jurisdiction_ocdid` are the export's own join-time additions (not real
    columns on `memberships`); `is_open` is computed from `closed_at` and not stored either;
    `meta_unmatched_text` is not published at all (see `parquet_rows.py`) so it never appears
    in the input in the first place. `post_id` is remapped: exports from before 218 carry
    random post ids, and the seed re-keys them."""
    row = membership_row(
        {
            "state": "wa",
            "id": "44444444-4444-4444-4444-444444444444",
            "person_id": "33333333-3333-3333-3333-333333333333",
            "post_id": "22222222-2222-2222-2222-222222222222",
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "jurisdiction_ocdid": _OCDID,
            "label": "Council Member",
            "start_date": "2024-01-01",
            "end_date": None,
            "opened_at": "2026-01-01T00:00:00Z",
            "last_seen_at": "2026-01-01T00:00:00Z",
            "closed_at": None,
            "created_at": "2026-01-01T00:00:00Z",
            "designations": ["Place 2"],
            "source_labels": ["Council Member, Place 2"],
            "is_open": True,
        },
        {"22222222-2222-2222-2222-222222222222": "post-by-key"},
    )

    assert "state" not in row
    assert "jurisdiction_ocdid" not in row
    assert "is_open" not in row
    assert row["designations"] == ["Place 2"]
    assert row["post_id"] == "post-by-key"


@pytest.mark.unit
def test_rows_in_jurisdictions_filters_to_the_given_set():
    rows = [
        {"jurisdiction_ocdid": "a", "value": 1},
        {"jurisdiction_ocdid": "b", "value": 2},
        {"jurisdiction_ocdid": "c", "value": 3},
    ]

    assert rows_in_jurisdictions(rows, {"a", "c"}) == [
        {"jurisdiction_ocdid": "a", "value": 1},
        {"jurisdiction_ocdid": "c", "value": 3},
    ]


@pytest.mark.unit
def test_rows_in_jurisdictions_empty_set_keeps_nothing():
    rows = [{"jurisdiction_ocdid": "a", "value": 1}]

    assert rows_in_jurisdictions(rows, set()) == []


@pytest.mark.unit
def test_limit_none_loads_every_organization():
    """`[:None]` is the whole list, so all of a state is `--states ca --limit none`."""
    assert limit_arg(NO_LIMIT) is None
    assert limit_arg("10") == 10


@pytest.mark.unit
def test_states_are_lowercased_like_the_jurisdictions_column():
    assert states_arg(" CA,wa ,") == ["ca", "wa"]
    assert states_arg("") == []
