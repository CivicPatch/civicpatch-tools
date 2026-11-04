"""The charter search prompt: how it names the place, the state's charter terms and the site."""

import pytest

from services.google_gemini.prompts import charter_search_prompt

pytestmark = pytest.mark.unit

_LANE = "ocd-jurisdiction/country:us/state:or/county:lane/government"


def test_the_charter_search_names_the_place_the_states_charter_terms_and_its_site():
    prompt = charter_search_prompt(_LANE, "Lane County", ["Charter", "Home Rule Charter"], "https://www.lanecountyor.gov")

    assert "Lane County, Oregon" in prompt
    assert '"Charter" or "Home Rule Charter"' in prompt
    assert "Its official website is https://www.lanecountyor.gov." in prompt
    assert '"charter_urls"' in prompt


def test_the_charter_search_gives_no_site_hint_when_the_registry_has_none():
    assert "official website" not in charter_search_prompt(_LANE, "Lane County", ["Charter"], None)
