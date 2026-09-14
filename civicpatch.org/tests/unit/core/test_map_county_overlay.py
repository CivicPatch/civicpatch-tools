"""Unit tests for local_county_ocdids — the spatial overlay that tells a place which
county (or counties, if it straddles a line) it belongs to. Real geometry, no mocks.
"""

import geopandas
import pytest
from shapely.geometry import box

from core.map_county_overlay import local_county_ocdids
from core.map_enrichment import GeoidEntry

pytestmark = pytest.mark.unit

_COUNTY_A = "ocd-jurisdiction/country:us/state:zz/county:a/government"
_COUNTY_B = "ocd-jurisdiction/country:us/state:zz/county:b/government"


def _counties_gdf():
    return geopandas.GeoDataFrame(
        {"GEOID": ["001", "002"]},
        geometry=[box(-100, 40, -96, 45), box(-96, 40, -90, 45)],
        crs="EPSG:4326",
    )


def _lookup():
    return {
        "001": GeoidEntry(_COUNTY_A, "County A"),
        "002": GeoidEntry(_COUNTY_B, "County B"),
    }


def _local_gdf(rows):
    return geopandas.GeoDataFrame(
        {"GEOID": [geoid for geoid, _geom in rows]},
        geometry=[geom for _geoid, geom in rows],
        crs="EPSG:4326",
    )


def test_feature_fully_inside_one_county():
    local = _local_gdf([("9001", box(-99, 41, -97, 44))])  # entirely within county A
    result = local_county_ocdids(local, _counties_gdf(), _lookup())
    assert result == {"9001": [_COUNTY_A]}


def test_straddling_feature_orders_by_descending_share():
    # -99 to -95 spans both counties: 3/4 of it (-99 to -96) sits in A, 1/4 (-96 to -95) in B.
    local = _local_gdf([("9002", box(-99, 41, -95, 44))])
    result = local_county_ocdids(local, _counties_gdf(), _lookup())
    assert result == {"9002": [_COUNTY_A, _COUNTY_B]}


def test_feature_with_no_county_overlap_is_excluded():
    local = _local_gdf([("9003", box(50, 50, 51, 51))])
    result = local_county_ocdids(local, _counties_gdf(), _lookup())
    assert result == {}


def test_multiple_features_keyed_by_own_geoid():
    local = _local_gdf(
        [
            ("9001", box(-99, 41, -97, 44)),
            ("9004", box(-93, 41, -91, 44)),
        ]
    )
    result = local_county_ocdids(local, _counties_gdf(), _lookup())
    assert result == {"9001": [_COUNTY_A], "9004": [_COUNTY_B]}
