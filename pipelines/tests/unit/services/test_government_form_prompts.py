"""The government form prompts: which forms they offer and how they name the place.

Wording is judged by `evalsg`; these pin what reaches the prompt at all.
"""

import pytest

from services.google_gemini.prompts import county_government_form_prompt, municipal_government_form_prompt
from shared.schemas import GovernmentForm

pytestmark = pytest.mark.unit

_SEATTLE = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_KING = "ocd-jurisdiction/country:us/state:wa/county:king/government"


def test_a_municipal_prompt_offers_only_the_forms_it_is_given():
    prompt = municipal_government_form_prompt(
        _SEATTLE, "Seattle city", [GovernmentForm.MAYOR_COUNCIL, GovernmentForm.COUNCIL_MANAGER]
    )

    assert "- mayor_council:" in prompt
    assert "- council_manager:" in prompt
    assert "open_town_meeting" not in prompt
    assert "Seattle city, Washington" in prompt


def test_a_county_prompt_describes_commission_as_a_county_board():
    prompt = county_government_form_prompt(
        _KING, "King County", [GovernmentForm.COMMISSION, GovernmentForm.COUNTY_EXECUTIVE]
    )

    assert "- commission: one elected board" in prompt
    assert "each head a department" not in prompt
    assert "presiding county judge" in prompt


def test_a_county_is_not_named_twice():
    prompt = county_government_form_prompt(_KING, "King County", [GovernmentForm.COMMISSION])

    assert "King County, Washington" in prompt
    assert "King County, King County" not in prompt


def test_both_prompts_ask_for_the_value_and_its_source():
    prompt = municipal_government_form_prompt(_SEATTLE, "Seattle city", [GovernmentForm.MAYOR_COUNCIL])

    assert '"government_form": "<value>"' in prompt
    assert '"source": "<url you relied on>"' in prompt
