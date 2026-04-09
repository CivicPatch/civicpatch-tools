import pytest
import yaml
from unittest.mock import AsyncMock, patch, call

from services.github.data_sync_service import get_jurisdiction_metadata, od_sync as bulk_sync

LACY_LAKEVIEW_OCDID = "ocd-jurisdiction/country:us/state:tx/place:lacy-lakeview/government"
AUSTIN_OCDID = "ocd-jurisdiction/country:us/state:tx/place:austin/government"


def _entries_yml(entries):
    return yaml.dump({"jurisdictions": entries})


def _metadata_yml(by_id):
    return yaml.dump({"jurisdictions_by_id": by_id})


def _mock_github(metadata_response, entries_response):
    return patch(
        "services.github.data_sync_service.github_service.get_github_file_contents",
        new=AsyncMock(side_effect=[metadata_response, entries_response]),
    )


# ── get_jurisdiction_metadata ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jurisdiction_in_both_files_is_merged():
    entries = _entries_yml([{"id": LACY_LAKEVIEW_OCDID, "name": "Lacy-Lakeview city"}])
    metadata = _metadata_yml({LACY_LAKEVIEW_OCDID: {"updated_at": "2026-03-28T04:34:32+00:00"}})

    with _mock_github(metadata, entries):
        result = await get_jurisdiction_metadata("tx")

    assert LACY_LAKEVIEW_OCDID in result
    assert result[LACY_LAKEVIEW_OCDID]["jurisdiction"]["name"] == "Lacy-Lakeview city"
    assert result[LACY_LAKEVIEW_OCDID]["updated_at"] == "2026-03-28T04:34:32+00:00"


@pytest.mark.asyncio
async def test_jurisdiction_in_entries_only_is_included():
    """Jurisdiction present in jurisdictions.yml but absent from jurisdictions_metadata.yml must still be returned."""
    entries = _entries_yml([{"id": LACY_LAKEVIEW_OCDID, "name": "Lacy-Lakeview city"}])
    metadata = _metadata_yml({})

    with _mock_github(metadata, entries):
        result = await get_jurisdiction_metadata("tx")

    assert LACY_LAKEVIEW_OCDID in result
    assert result[LACY_LAKEVIEW_OCDID]["jurisdiction"]["name"] == "Lacy-Lakeview city"


@pytest.mark.asyncio
async def test_jurisdiction_in_metadata_only_is_excluded():
    """Jurisdiction absent from jurisdictions.yml should not appear even if it has metadata."""
    entries = _entries_yml([])
    metadata = _metadata_yml({LACY_LAKEVIEW_OCDID: {"updated_at": "2026-03-28T04:34:32+00:00"}})

    with _mock_github(metadata, entries):
        result = await get_jurisdiction_metadata("tx")

    assert LACY_LAKEVIEW_OCDID not in result


@pytest.mark.asyncio
async def test_entry_without_id_is_skipped():
    entries = _entries_yml([
        {"name": "No ID Entry"},
        {"id": LACY_LAKEVIEW_OCDID, "name": "Lacy-Lakeview city"},
    ])
    metadata = _metadata_yml({})

    with _mock_github(metadata, entries):
        result = await get_jurisdiction_metadata("tx")

    assert len(result) == 1
    assert LACY_LAKEVIEW_OCDID in result


@pytest.mark.asyncio
async def test_multiple_jurisdictions_mixed_metadata():
    entries = _entries_yml([
        {"id": LACY_LAKEVIEW_OCDID, "name": "Lacy-Lakeview city"},
        {"id": AUSTIN_OCDID, "name": "Austin city"},
    ])
    metadata = _metadata_yml({AUSTIN_OCDID: {"updated_at": "2026-01-01"}})

    with _mock_github(metadata, entries):
        result = await get_jurisdiction_metadata("tx")

    assert LACY_LAKEVIEW_OCDID in result
    assert AUSTIN_OCDID in result
    assert result[AUSTIN_OCDID]["updated_at"] == "2026-01-01"
    assert "updated_at" not in result[LACY_LAKEVIEW_OCDID]


@pytest.mark.asyncio
async def test_returns_none_when_metadata_file_missing():
    with _mock_github(None, _entries_yml([])):
        result = await get_jurisdiction_metadata("tx")

    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_entries_file_missing():
    with _mock_github(_metadata_yml({}), None):
        result = await get_jurisdiction_metadata("tx")

    assert result is None


# ── bulk_sync: people_count=0 forces people sync ─────────────────────────────

MOUNTAIN_CITY_OCDID = "ocd-jurisdiction/country:us/state:tx/place:mountain_city/government"

def _mock_bulk_sync_deps(remote_metadata, local_jurisdictions):
    """Patch all external calls used by bulk_sync."""
    return (
        patch("services.github.data_sync_service.config_utils.get_states", return_value=[{"code": "tx"}]),
        patch("services.github.data_sync_service.get_jurisdiction_metadata", new=AsyncMock(return_value=remote_metadata)),
        patch("services.github.data_sync_service.database.get_jurisdiction_updates", new=AsyncMock(return_value=local_jurisdictions)),
        patch("services.github.data_sync_service.database.deactivate_jurisdictions_by_ocdids", new=AsyncMock()),
        patch("services.github.data_sync_service.sync_jurisdictions_by_ocdids_with_metadata", new=AsyncMock()),
        patch("services.github.data_sync_service.sync_people_by_ocdids", new=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_bulk_sync_skips_people_when_up_to_date_and_has_people():
    """Jurisdiction with current updated_at and existing people is not re-synced."""
    remote = {MOUNTAIN_CITY_OCDID: {"updated_at": "2026-02-12T18:46:34+00:00", "jurisdiction": {"id": MOUNTAIN_CITY_OCDID}}}
    local = {MOUNTAIN_CITY_OCDID: {"updated_at": "2026-02-12T18:46:34+00:00", "people_count": 3}}

    patches = _mock_bulk_sync_deps(remote, local)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as mock_sync_people:
        await bulk_sync()

    mock_sync_people.assert_called_once_with([])


@pytest.mark.asyncio
async def test_bulk_sync_syncs_people_when_no_people_in_db():
    """Jurisdiction with zero people is re-synced when remote has a valid updated_at, even if timestamps match."""
    remote = {MOUNTAIN_CITY_OCDID: {"updated_at": "2026-02-12T18:46:34+00:00", "jurisdiction": {"id": MOUNTAIN_CITY_OCDID}}}
    local = {MOUNTAIN_CITY_OCDID: {"updated_at": "2026-02-12T18:46:34+00:00", "people_count": 0}}

    patches = _mock_bulk_sync_deps(remote, local)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as mock_sync_people:
        await bulk_sync()

    mock_sync_people.assert_called_once_with([MOUNTAIN_CITY_OCDID])


@pytest.mark.asyncio
async def test_bulk_sync_skips_people_when_no_people_and_no_remote_updated_at():
    """Jurisdiction with zero people is NOT re-synced when remote has no updated_at."""
    remote = {MOUNTAIN_CITY_OCDID: {"jurisdiction": {"id": MOUNTAIN_CITY_OCDID}}}
    local = {MOUNTAIN_CITY_OCDID: {"updated_at": "2026-02-12T18:46:34+00:00", "people_count": 0}}

    patches = _mock_bulk_sync_deps(remote, local)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as mock_sync_people:
        await bulk_sync()

    mock_sync_people.assert_called_once_with([])


@pytest.mark.asyncio
async def test_bulk_sync_syncs_people_for_new_jurisdiction():
    """Jurisdiction not yet in DB (never synced) is synced even if remote updated_at is old."""
    remote = {MOUNTAIN_CITY_OCDID: {"updated_at": "2026-02-12T18:46:34+00:00", "jurisdiction": {"id": MOUNTAIN_CITY_OCDID}}}
    local = {}

    patches = _mock_bulk_sync_deps(remote, local)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as mock_sync_people:
        await bulk_sync()

    mock_sync_people.assert_called_once_with([MOUNTAIN_CITY_OCDID])
