"""Vermont's index decides: listed is a charter at its full text, not listed is general law.
The wording and the link rewrite come from config, as Vermont's file gives them."""

from pathlib import Path

import pytest

from runners.governing_law_collector.finders.state_index import charter_links, charter_title_matches
from shared.utils.layered_config import CharterLinkList

pytestmark = pytest.mark.unit

INDEX = (Path(__file__).parent / "fixtures" / "vt_24_appendix_index.html").read_bytes()
INDEX_URL = "https://legislature.vermont.gov/statutes/title/24APPENDIX"
FULL_TEXT = "https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/"
VERMONT = CharterLinkList(
    url=INDEX_URL,
    title="Chapter {*} : {lsad} of {place}",
    text_link={"old": "/statutes/chapter/", "new": "/statutes/fullchapter/"},
)


def _chapters(name: str) -> list[str]:
    return [url.removeprefix(FULL_TEXT) for url in charter_links(VERMONT, INDEX, INDEX_URL, name)]


def test_a_place_matches_its_chapter_by_lsad_and_name():
    assert _chapters("Stowe town") == ["149"]
    assert _chapters("Barre city") == ["001"]
    assert _chapters("Barre town") == ["101"]
    assert _chapters("St. Albans city") == ["011"]
    assert _chapters("Northfield town") == ["129D"]


def test_a_place_with_two_chapters_gets_both():
    assert _chapters("Winooski city") == ["017", "019"]


def test_a_place_not_in_the_index_has_no_charter():
    assert _chapters("Weathersfield town") == []


def test_a_title_marked_repealed_is_no_charter():
    """Essex Junction village's chapter says so; the city's charter stands."""
    assert _chapters("Essex Junction village") == []
    assert _chapters("Essex Junction city") == ["004"]


def test_a_link_outside_the_list_that_names_the_place_is_not_its_charter():
    """The fixture's footer links "Visiting the Town of Stowe": only the exact title counts."""
    assert _chapters("Stowe town") == ["149"]


def test_without_a_text_link_the_index_link_is_the_text():
    plain_index = VERMONT.model_copy(update={"text_link": None})

    assert charter_links(plain_index, INDEX, INDEX_URL, "Stowe town") == [
        "https://legislature.vermont.gov/statutes/chapter/24APPENDIX/149"
    ]


_VERMONT_TITLE = "Chapter {*} : {lsad} of {place}"


def test_a_charter_title_matches_the_whole_link_text():
    assert charter_title_matches(_VERMONT_TITLE, "Stowe town", "Chapter  149 :  Town of Stowe")
    assert charter_title_matches(_VERMONT_TITLE, "St. Albans city", "Chapter 011 : City of St. Albans")
    assert charter_title_matches(_VERMONT_TITLE, "Northfield town", "Chapter 129D : Town of Northfield")


def test_a_title_with_anything_more_or_less_does_not_match():
    assert not charter_title_matches(_VERMONT_TITLE, "Essex Junction village", "Chapter 221 : Village of Essex Junction [Repealed]")
    assert not charter_title_matches(_VERMONT_TITLE, "Stowe town", "Visiting the Town of Stowe")
    assert not charter_title_matches(_VERMONT_TITLE, "Barre town", "Chapter 001 : City of Barre")


def test_a_state_that_lists_charters_by_place_alone_needs_no_lsad():
    assert charter_title_matches("{place}", "Dover city", "Dover")
