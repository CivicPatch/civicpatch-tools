"""The law search prompt: how it names the place, the target, the state's terms and the site."""

import pytest

from services.google_gemini.prompts import law_search_prompt

pytestmark = pytest.mark.unit

_LANE = "ocd-jurisdiction/country:us/state:or/county:lane/government"


def _prompt(url: str | None = "https://www.lanecountyor.gov") -> str:
    return law_search_prompt(_LANE, "Lane County", "charter", "municipal or county charter", ["Charter", "Home Rule Charter"], url)


def test_the_search_names_the_place_the_target_the_states_terms_and_its_site():
    prompt = _prompt()

    assert "the current municipal or county charter of Lane County, Oregon" in prompt
    assert '"Charter" or "Home Rule Charter"' in prompt
    assert "no charter online" in prompt
    assert "Its official website is https://www.lanecountyor.gov." in prompt
    assert '"urls"' in prompt


def test_the_search_gives_no_site_hint_when_the_registry_has_none():
    assert "official website" not in _prompt(None)
