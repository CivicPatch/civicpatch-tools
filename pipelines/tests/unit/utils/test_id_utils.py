import json
from pathlib import Path

import pytest
from shared.utils.id_utils import (  # Replace `your_module` with the actual module name
    folder_to_jurisdiction_ocdid,
    jurisdiction_ocdid_to_folder,
    make_git_branch,
    parse_jurisdiction_ocdid,
    slug_to_jurisdiction_ocdid,
)

pytestmark = pytest.mark.unit

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "shared"
    / "tests"
    / "fixtures"
    / "ocdid_paths.json"
)


# Mock class for JurisdictionId
class JurisdictionId:
    def __init__(
        self,
        country,
        state,
        county=None,
        place_label=None,
        place=None,
        jurisdiction_type=None,
    ):
        self.country = country
        self.state = state
        self.county = county
        self.place_label = place_label
        self.place = place
        self.jurisdiction_type = jurisdiction_type

    def __eq__(self, other):
        return (
            self.country == other.country
            and self.state == other.state
            and self.county == other.county
            and self.place_label == other.place_label
            and self.place == other.place
            and self.jurisdiction_type == other.jurisdiction_type
        )


# Tests for parse_jurisdiction_ocdid
def test_parse_jurisdiction_ocdid_valid():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
    expected = JurisdictionId(
        country="us",
        state="wa",
        county=None,
        place_label="place",
        place="seattle",
        jurisdiction_type="government",
    )
    assert parse_jurisdiction_ocdid(jurisdiction_ocdid) == expected


def test_parse_jurisdiction_ocdid_with_county():
    jurisdiction_ocdid = (
        "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government"
    )
    expected = JurisdictionId(
        country="us",
        state="il",
        county="dupage",
        place_label="place",
        place="naperville",
        jurisdiction_type="government",
    )
    assert parse_jurisdiction_ocdid(jurisdiction_ocdid) == expected


def test_parse_jurisdiction_ocdid_invalid_format():
    jurisdiction_ocdid = "invalid-format"
    # Should throw a ValueError
    with pytest.raises(ValueError, match="Invalid jurisdiction ID format"):
        parse_jurisdiction_ocdid(jurisdiction_ocdid)


# Tests for jurisdiction_ocdid_to_folder
def test_jurisdiction_ocdid_to_folder():
    jurisdiction_ocdid = (
        "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/council"
    )
    expected = "il/local/county_dupage__place_naperville"
    assert jurisdiction_ocdid_to_folder(jurisdiction_ocdid) == expected


# Shared fixture also consumed by the frontend vitest suite
# (civicpatch.org/src/frontend/tests/ocdid-utils.test.ts) — keeps the JS
# jurisdictionOcdidToPath helper in sync with the Python implementation.
@pytest.mark.parametrize("case", json.loads(_FIXTURE_PATH.read_text()))
def test_jurisdiction_ocdid_to_folder_shared_fixture(case):
    assert jurisdiction_ocdid_to_folder(case["ocdid"]) == case["path"]


# Tests for make_git_branch
def test_make_git_branch():
    jurisdiction_ocdid = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
    pipeline_run_id = "2025-09-25-1a2b"
    expected = "2025-09-25-1a2b__state_wa__place_seattle__government"
    assert make_git_branch(jurisdiction_ocdid, pipeline_run_id) == expected


def test_make_git_branch_encodes_tilde():
    jurisdiction_ocdid = (
        "ocd-jurisdiction/country:us/state:ca/place:st~helena/government"
    )
    pipeline_run_id = "2025-09-25-1a2b"
    branch = make_git_branch(jurisdiction_ocdid, pipeline_run_id)
    assert "~" not in branch
    assert "--" in branch


# Tests for slug_to_jurisdiction_ocdid
def test_slug_to_jurisdiction_ocdid():
    slug = "state_ca__county_marin__special_district_marin_city_community_services_district__governing_board"
    expected = "ocd-jurisdiction/country:us/state:ca/county:marin/special_district:marin_city_community_services_district/governing_board"
    assert slug_to_jurisdiction_ocdid(slug) == expected


def test_slug_to_jurisdiction_ocdid_invalid():
    slug = "invalid_slug_format"
    with pytest.raises(ValueError, match="Slug must start with 'state'."):
        slug_to_jurisdiction_ocdid(slug)


@pytest.mark.parametrize("case", json.loads(_FIXTURE_PATH.read_text()))
def test_folder_round_trips_back_to_the_ocdid(case):
    assert folder_to_jurisdiction_ocdid(case["path"]) == case["ocdid"]


def test_a_county_with_no_place_is_the_jurisdiction():
    assert (
        folder_to_jurisdiction_ocdid("tx/local/county_travis")
        == "ocd-jurisdiction/country:us/state:tx/county:travis/government"
    )
