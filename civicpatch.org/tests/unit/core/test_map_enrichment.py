"""Unit tests for the pmtiles feature-enrichment functions. Pure, no mocks — stamps a
GEOID-keyed jurisdiction_ocdid (and, for local features, the canonical name) onto raw
TIGER GeoJSON features before tippecanoe tiles them.
"""

import pytest

from core.map_enrichment import (
    GeoidEntry,
    enrich_county_feature,
    enrich_local_feature,
    enrich_state_feature,
    feature_collection,
)

pytestmark = pytest.mark.unit


class TestEnrichStateFeature:
    def _feature(self):
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[]]},
            "properties": {
                "STATEFP": "08", "GEOID": "08", "STUSPS": "CO", "NAME": "Colorado",
                "ALAND": 268596070292,
            },
        }

    def _lookup(self):
        return {"08": GeoidEntry("ocd-jurisdiction/country:us/state:co/government", "Colorado")}

    def test_sets_jurisdiction_ocdid_from_lookup(self):
        result = enrich_state_feature(self._feature(), self._lookup())
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:co/government"

    def test_sets_geoid_name_code(self):
        result = enrich_state_feature(self._feature(), self._lookup())
        assert result["properties"]["geoid"] == "08"
        assert result["properties"]["name"] == "Colorado"
        assert result["properties"]["code"] == "co"

    def test_strips_census_properties(self):
        result = enrich_state_feature(self._feature(), self._lookup())
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name", "code"}

    def test_empty_string_when_geoid_not_in_lookup(self):
        result = enrich_state_feature(self._feature(), {})
        assert result["properties"]["jurisdiction_ocdid"] == ""


class TestEnrichCountyFeature:
    def _feature(self):
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[]]},
            "properties": {
                "STATEFP": "08", "GEOID": "08001", "NAME": "Adams", "NAMELSAD": "Adams County",
                "ALAND": 1259928850,
            },
        }

    def _lookup(self):
        return {
            "08001": GeoidEntry(
                "ocd-jurisdiction/country:us/state:co/county:adams/government", "Adams County"
            )
        }

    def test_sets_jurisdiction_ocdid_from_lookup(self):
        result = enrich_county_feature(self._feature(), self._lookup())
        assert (
            result["properties"]["jurisdiction_ocdid"]
            == "ocd-jurisdiction/country:us/state:co/county:adams/government"
        )

    def test_sets_name_from_namelsad_not_lookup(self):
        # Unlike local features, county name comes straight off the TIGER feature.
        result = enrich_county_feature(self._feature(), self._lookup())
        assert result["properties"]["name"] == "Adams County"

    def test_strips_census_properties(self):
        result = enrich_county_feature(self._feature(), self._lookup())
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name"}

    def test_empty_string_when_geoid_not_in_lookup(self):
        result = enrich_county_feature(self._feature(), {})
        assert result["properties"]["jurisdiction_ocdid"] == ""


class TestEnrichLocalFeature:
    def _lookup(self):
        return {
            "0820000": GeoidEntry(
                "ocd-jurisdiction/country:us/state:co/place:denver/government", "Denver city"
            )
        }

    def _feature(self, geoid="0820000", county_ocdids=None):
        props = {"GEOID": geoid, "NAME": "Denver", "ALAND": 12345}
        if county_ocdids is not None:
            props["county_ocdids"] = county_ocdids
        return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[]]}, "properties": props}

    def test_matched_feature_takes_name_from_lookup_not_tiger(self):
        # The whole reason local enrichment needs more than an ocdid: TIGER's raw place
        # name can disagree with the canonical one (formatting, suffix conventions).
        result = enrich_local_feature(self._feature(), self._lookup())
        assert result is not None
        assert result["properties"]["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:co/place:denver/government"
        assert result["properties"]["geoid"] == "0820000"
        assert result["properties"]["name"] == "Denver city"
        assert result["properties"]["county_ocdids"] == []

    def test_passes_through_county_ocdids(self):
        parents = ["ocd-jurisdiction/country:us/state:co/county:denver/government"]
        result = enrich_local_feature(self._feature(county_ocdids=parents), self._lookup())
        assert result is not None
        assert result["properties"]["county_ocdids"] == parents

    def test_matched_feature_strips_census_properties(self):
        result = enrich_local_feature(self._feature(), self._lookup())
        assert set(result["properties"].keys()) == {"jurisdiction_ocdid", "geoid", "name", "county_ocdids"}

    def test_unmatched_feature_returns_none(self):
        result = enrich_local_feature(self._feature("9999999"), self._lookup())
        assert result is None

    def test_handles_lowercase_geoid_key(self):
        feature = {"type": "Feature", "geometry": {}, "properties": {"geoid": "0820000"}}
        result = enrich_local_feature(feature, self._lookup())
        assert result is not None


def test_feature_collection_wraps_features():
    features = [{"type": "Feature"}]
    assert feature_collection(features) == {"type": "FeatureCollection", "features": features}
