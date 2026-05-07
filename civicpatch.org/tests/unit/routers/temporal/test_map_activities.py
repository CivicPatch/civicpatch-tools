import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from temporalio.testing import ActivityEnvironment

from routers.temporal.map_activities import (
    _enrich_geojson,
    sync_jurisdiction_map_activity,
)

SAMPLE_GEOID_MAP = {
    "3451000": {"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:nj/place:newark/government", "name": "Newark city"},
    "3473960": {"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:nj/place:trenton/government", "name": "Trenton city"},
}

SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[]]}, "properties": {"GEOID": "3451000", "NAME": "Newark", "EXTRA": "ignored"}},
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[]]}, "properties": {"GEOID": "9999999", "NAME": "Unknown"}},
    ],
}


def test_enrich_geojson_keeps_only_matched_features():
    result = _enrich_geojson(SAMPLE_GEOJSON, SAMPLE_GEOID_MAP)
    assert len(result["features"]) == 1
    feat = result["features"][0]
    assert feat["properties"]["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:nj/place:newark/government"
    assert feat["properties"]["name"] == "Newark city"
    assert "EXTRA" not in feat["properties"]
    assert "NAME" not in feat["properties"]


def test_enrich_geojson_handles_lowercase_geoid():
    geojson_lower = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {}, "properties": {"geoid": "3451000"}},
        ],
    }
    result = _enrich_geojson(geojson_lower, SAMPLE_GEOID_MAP)
    assert len(result["features"]) == 1


def test_enrich_geojson_empty_when_no_matches():
    result = _enrich_geojson(SAMPLE_GEOJSON, {})
    assert result["features"] == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_sync_jurisdiction_map_activity_returns_url():
    env_vars = {
        "STORAGE_ENDPOINT": "https://endpoint.example.com",
        "STORAGE_ACCESS_KEY_ID": "key",
        "STORAGE_SECRET_ACCESS_KEY": "secret",
        "FRIENDLY_STORAGE_HOST": "https://cdn.civicpatch.org",
    }

    geojson_response = MagicMock()
    geojson_response.text = json.dumps(SAMPLE_GEOJSON)
    geojson_response.raise_for_status = MagicMock()

    activity_env = ActivityEnvironment()
    with patch("routers.temporal.map_activities.get_env_vars", return_value=env_vars), \
         patch("routers.temporal.map_activities.jurisdictions_db.get_jurisdictions_by_geoid", new_callable=AsyncMock, return_value=SAMPLE_GEOID_MAP), \
         patch("routers.temporal.map_activities.httpx.AsyncClient") as mock_client_cls, \
         patch("routers.temporal.map_activities.subprocess.run") as mock_run, \
         patch("routers.temporal.map_activities.boto3.client") as mock_boto:

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=geojson_response)
        mock_client_cls.return_value = mock_client

        mock_run.return_value = MagicMock(returncode=0)
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        result = await activity_env.run(sync_jurisdiction_map_activity, "nj")

    assert result == "https://cdn.civicpatch.org/maps/nj.pmtiles"
    mock_s3.upload_file.assert_called_once()
