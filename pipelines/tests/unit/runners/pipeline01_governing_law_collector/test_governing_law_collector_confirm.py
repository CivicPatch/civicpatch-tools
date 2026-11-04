"""The rule that keeps a charter and rejects a page that only mentions one, with the shapes the
crawl met: a real charter, a news item, a "Government" page, a move notice, a soft 404."""

import pytest
from runners.pipeline01_governing_law_collector.finders.confirm import MIN_CHARTER_CHARS, is_charter, place_word

pytestmark = pytest.mark.unit

TERMS = ["Charter", "Home Rule Charter"]
_CLAUSE = "Section {n}. The board of county commissioners shall consist of five county commissioners elected by district. "


def _charter(name_in_text: str, sections: int = 60) -> str:
    return f"HOME RULE CHARTER FOR {name_in_text}\n\n" + "".join(_CLAUSE.format(n=n) for n in range(1, sections + 1))


def test_a_charter_naming_its_place_with_many_sections_is_one():
    assert is_charter(_charter("LANE COUNTY"), "Lane County", TERMS)


def test_a_news_item_that_mentions_the_charter_is_not():
    news = "Stowe charter change testimony: the selectboard heard residents on the proposed charter change Tuesday night. " * 60

    assert len(news) >= MIN_CHARTER_CHARS
    assert not is_charter(news, "Stowe town", TERMS)


def test_a_short_landing_page_is_not():
    assert not is_charter("County Charter\n\nDownload the Hood River County charter (PDF). Section 1. Section 2.", "Hood River County", TERMS)


def test_another_places_charter_is_not():
    assert not is_charter(_charter("BENTON COUNTY"), "Lane County", TERMS)


def test_a_soft_404_is_not():
    assert not is_charter("Page not found\n\n" + _charter("ALBANY"), "Albany", TERMS)


def test_a_charter_with_a_street_number_404_in_its_heading_is_one():
    assert is_charter("City Hall, 404 Main Street\n\n" + _charter("ALBANY"), "Albany", TERMS)


def test_the_charter_term_may_be_any_the_state_uses():
    text = _charter("LANE COUNTY").replace("HOME RULE CHARTER", "CHARTER")

    assert is_charter(text, "Lane County", TERMS)
    assert not is_charter(text.replace("CHARTER", "CODE"), "Lane County", TERMS)


@pytest.mark.parametrize(
    "name,word",
    [("Lane County", "lane"), ("Lakeview town", "lakeview"), ("Portland city", "portland"), ("Portland", "portland"), ("Hyde Park village", "hyde park")],
)
def test_the_place_word_drops_the_registrys_status_word(name: str, word: str):
    assert place_word(name) == word
