import pytest 
from jobs.people_collector.steps.step_08_format_output.format_output import normalize_division

pytestmark = pytest.mark.unit

def test_normalize_division_with_geographic_area():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = "ward 3"
    division_configs = {
        "ward": {
            "has_geographic_area": True,
            "name": "ward"
        }
    }
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne/ward:3"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid

def test_normalize_division_without_geographic_area():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = "ward 3"
    division_configs = {
        "ward": {
            "has_geographic_area": False,
            "name": "ward"
        }
    }
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid

def test_normalize_division_empty_string():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = None
    division_configs = {}
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid

def test_normalize_division_unknown_key():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:nj/place:bayonne/government"
    division_string = "unknown 1"
    division_configs = {}
    expected_division_ocdid = "ocd-division/country:us/state:nj/place:bayonne"
    assert normalize_division(jurisdiction_ocdid, division_string, division_configs) == expected_division_ocdid