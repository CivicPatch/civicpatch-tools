from unittest.mock import patch

import geopandas
import pytest
from shapely.geometry import box

from lib import tiger

pytestmark = pytest.mark.unit


def _write_fixture_shapefile(tmp_path):
    gdf = geopandas.GeoDataFrame(
        {"STATEFP": ["06", "08"]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)],
        crs="EPSG:4326",
    )
    shp_path = tmp_path / "fixture.shp"
    gdf.to_file(shp_path)
    return shp_path


def test_fetch_national_states_filters_to_fips(tmp_path):
    shp_path = _write_fixture_shapefile(tmp_path)

    with patch("lib.tiger._download_and_extract", return_value=shp_path) as mock_fetch:
        result = tiger.fetch_national_states("06")

    mock_fetch.assert_called_once()
    assert list(result["STATEFP"]) == ["06"]


def test_fetch_national_counties_filters_to_fips(tmp_path):
    shp_path = _write_fixture_shapefile(tmp_path)

    with patch("lib.tiger._download_and_extract", return_value=shp_path):
        result = tiger.fetch_national_counties("08")

    assert list(result["STATEFP"]) == ["08"]


def test_fetch_all_states_returns_every_row(tmp_path):
    shp_path = _write_fixture_shapefile(tmp_path)

    with patch("lib.tiger._download_and_extract", return_value=shp_path):
        result = tiger.fetch_all_states()

    assert sorted(result["STATEFP"]) == ["06", "08"]


def test_place_and_cousub_urls_are_state_scoped():
    assert "tl_2025_06_place.zip" in tiger._place_shp_url("06")
    assert "tl_2025_06_cousub.zip" in tiger._cousub_shp_url("06")
