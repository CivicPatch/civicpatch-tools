import pytest
import yaml
from unittest.mock import AsyncMock, patch

from services.github.data_sync_service import get_jurisdiction_metadata

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
