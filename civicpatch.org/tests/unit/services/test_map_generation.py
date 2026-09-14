"""Unit tests for generate_and_upload_state_pmtiles — the orchestration that wires
TIGER fetch, enrichment, the county overlay, tippecanoe, and the R2 upload together.

External boundaries are mocked (network fetch, subprocess, DB, storage); the enrichment
and county-overlay logic in between runs for real, on small synthetic geometry, so this
also exercises the wiring between those already-unit-tested pieces.
"""

import json
from unittest.mock import AsyncMock, patch

import geopandas
import pytest
from shapely.geometry import box

from core.map_enrichment import GeoidEntry
from services.map_generation import (
    generate_and_upload_national_overview,
    generate_and_upload_state_pmtiles,
)

pytestmark = pytest.mark.unit

_STATE_OCDID = "ocd-jurisdiction/country:us/state:co/government"
_COUNTY_OCDID = "ocd-jurisdiction/country:us/state:co/county:adams/government"
_PLACE_OCDID = "ocd-jurisdiction/country:us/state:co/place:denver/government"

_LOOKUP = {
    "08": GeoidEntry(_STATE_OCDID, "Colorado"),
    "08001": GeoidEntry(_COUNTY_OCDID, "Adams County"),
    "0820000": GeoidEntry(_PLACE_OCDID, "Denver city"),
}


def _state_gdf():
    return geopandas.GeoDataFrame(
        {"STATEFP": ["08"], "GEOID": ["08"], "STUSPS": ["CO"], "NAME": ["Colorado"]},
        geometry=[box(-100, 40, -96, 45)],
        crs="EPSG:4326",
    )


def _county_gdf():
    return geopandas.GeoDataFrame(
        {"STATEFP": ["08"], "GEOID": ["08001"], "NAMELSAD": ["Adams County"]},
        geometry=[box(-100, 40, -96, 45)],
        crs="EPSG:4326",
    )


def _places_gdf():
    # Fully inside the county above.
    return geopandas.GeoDataFrame(
        {"GEOID": ["0820000"], "NAME": ["Denver"]},
        geometry=[box(-99, 41, -97, 44)],
        crs="EPSG:4326",
    )


def _cousubs_gdf():
    # No overlap with anything, and no match in the lookup — should be dropped silently.
    return geopandas.GeoDataFrame(
        {"GEOID": ["9999999"], "NAME": ["Nowhere"]},
        geometry=[box(50, 50, 51, 51)],
        crs="EPSG:4326",
    )


def _fake_tippecanoe(layers, output_path, label=""):
    output_path.write_bytes(b"fake-pmtiles-bytes")


@pytest.mark.asyncio
async def test_generates_and_uploads_pmtiles_and_writes_parent_ocdids():
    with (
        patch("services.map_generation.get_state_fips", AsyncMock(return_value="08")),
        patch("services.map_generation.get_geoid_lookup", AsyncMock(return_value=_LOOKUP)),
        patch("services.map_generation.set_parent_ocdids", AsyncMock()) as mock_set_parents,
        patch("services.map_generation.tiger.fetch_national_states", return_value=_state_gdf()),
        patch("services.map_generation.tiger.fetch_national_counties", return_value=_county_gdf()),
        patch("services.map_generation.tiger.fetch_places", return_value=_places_gdf()),
        patch("services.map_generation.tiger.fetch_county_subdivisions", return_value=_cousubs_gdf()),
        patch("services.map_generation.tippecanoe.run_tippecanoe", side_effect=_fake_tippecanoe) as mock_tippecanoe,
        patch("services.map_generation.storage.upload_bytes_to_storage") as mock_upload,
        patch("services.map_generation.buckets.CDN", "test-cdn-bucket"),
        patch(
            "services.map_generation.environment.get_env_vars",
            return_value={"FRIENDLY_STORAGE_HOST": "https://cdn.example.com"},
        ),
    ):
        url = await generate_and_upload_state_pmtiles("co")

    assert url == "https://cdn.example.com/maps/co.pmtiles"

    # Three named layers, in the established order/minzooms.
    layers = mock_tippecanoe.call_args[0][0]
    assert [(name, minzoom) for name, _path, minzoom in layers] == [
        ("states", 0),
        ("counties", 5),
        ("local", 8),
    ]

    mock_upload.assert_called_once_with(
        "test-cdn-bucket", "maps/co.pmtiles", b"fake-pmtiles-bytes", "application/octet-stream"
    )

    # Denver is inside Adams county — parent_ocdids should chain county then state.
    mock_set_parents.assert_awaited_once_with({_PLACE_OCDID: [_COUNTY_OCDID, _STATE_OCDID]})


@pytest.mark.asyncio
async def test_raises_when_state_not_found():
    with patch("services.map_generation.get_state_fips", AsyncMock(return_value=None)):
        with pytest.raises(ValueError):
            await generate_and_upload_state_pmtiles("zz")


def _all_states_gdf():
    # Three states in TIGER, but only two are onboarded (present in the lookup) — the
    # third must be filtered out before it ever reaches enrichment.
    return geopandas.GeoDataFrame(
        {
            "STATEFP": ["08", "53", "06"],
            "GEOID": ["08", "53", "06"],
            "STUSPS": ["CO", "WA", "CA"],
            "NAME": ["Colorado", "Washington", "California"],
        },
        geometry=[box(-100, 40, -96, 45), box(-120, 45, -116, 49), box(-120, 32, -114, 42)],
        crs="EPSG:4326",
    )


@pytest.mark.asyncio
async def test_national_overview_filters_to_onboarded_states_and_uploads():
    lookup = {
        "08": GeoidEntry(_STATE_OCDID, "Colorado"),
        "53": GeoidEntry("ocd-jurisdiction/country:us/state:wa/government", "Washington"),
    }
    captured_layers = []

    def fake_tippecanoe(layers, output_path, label=""):
        # Read the geojson back before this call returns — the temp dir it lives in is
        # gone by the time the `with` block below exits.
        captured_layers.append(
            [(name, json.loads(path.read_text()), minzoom) for name, path, minzoom in layers]
        )
        output_path.write_bytes(b"fake-pmtiles-bytes")

    with (
        patch("services.map_generation.get_all_states_geoid_lookup", AsyncMock(return_value=lookup)),
        patch("services.map_generation.tiger.fetch_all_states", return_value=_all_states_gdf()),
        patch("services.map_generation.tippecanoe.run_tippecanoe", side_effect=fake_tippecanoe),
        patch("services.map_generation.storage.upload_bytes_to_storage") as mock_upload,
        patch("services.map_generation.buckets.CDN", "test-cdn-bucket"),
        patch(
            "services.map_generation.environment.get_env_vars",
            return_value={"FRIENDLY_STORAGE_HOST": "https://cdn.example.com"},
        ),
    ):
        url = await generate_and_upload_national_overview()

    assert url == "https://cdn.example.com/maps/states.pmtiles"
    mock_upload.assert_called_once_with(
        "test-cdn-bucket", "maps/states.pmtiles", b"fake-pmtiles-bytes", "application/octet-stream"
    )

    # Only the one named layer, and only the onboarded states' features in it.
    [(name, geojson, minzoom)] = captured_layers[0]
    assert (name, minzoom) == ("states", 0)
    assert {f["properties"]["code"] for f in geojson["features"]} == {"co", "wa"}
