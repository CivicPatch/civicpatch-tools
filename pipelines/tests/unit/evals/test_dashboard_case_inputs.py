"""Each case's prompt inputs, read from the real dataset, for the run browser to show."""

import pytest
from dashboard_data import read_case_inputs

pytestmark = pytest.mark.unit


def test_a_case_shows_its_prompt_inputs_and_not_its_answer():
    inputs = read_case_inputs("relevant_page")["millbury_school_committee_irrelevant"]

    assert inputs["government_form"] == "open_town_meeting"
    assert inputs["known_organizations"] == '["Select Board", "Town Meeting"]'
    assert "page" not in inputs


def test_page_covers_inputs_name_every_body_with_its_posts():
    inputs = read_case_inputs("page_covers")["millbury_school_committee"]

    assert '"name": "Select Board"' in inputs["organizations"]
    assert "covers" not in inputs
