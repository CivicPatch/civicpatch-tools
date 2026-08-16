import pytest
from shared.utils import url_utils


# format_url

def test_format_url_adds_scheme():
    assert url_utils.format_url("example.com") == "https://example.com"

def test_format_url_lowercases_scheme():
    # Full equality, not startswith: the prefix assertion passed on the broken output
    # "https://https://example.com/Path", which is exactly the bug it was named for.
    assert url_utils.format_url("HTTPS://example.com/Path") == "https://example.com/Path"

def test_format_url_does_not_prepend_a_second_scheme_to_an_uppercase_one():
    assert (
        url_utils.format_url("HTTP://WWW.LaPorteTX.gov/691/Mayor")
        == "http://www.laportetx.gov/691/Mayor"
    )

def test_format_url_adds_scheme_to_a_host_beginning_http():
    assert url_utils.format_url("httpbin.org/x") == "https://httpbin.org/x"

def test_format_url_lowercases_host():
    assert url_utils.format_url("https://EXAMPLE.COM/Path") == "https://example.com/Path"

def test_format_url_preserves_path_case():
    assert url_utils.format_url("https://example.com/CityCouncil") == "https://example.com/CityCouncil"

def test_format_url_preserves_trailing_slash():
    assert url_utils.format_url("https://example.com/path/") == "https://example.com/path/"

def test_format_url_preserves_www():
    assert url_utils.format_url("https://www.example.com/path") == "https://www.example.com/path"


# same_url

def test_same_url_www_vs_non_www():
    assert url_utils.same_url("https://www.example.com/path", "https://example.com/path")

def test_same_url_path_case_insensitive():
    assert url_utils.same_url("https://example.com/CityCouncil", "https://example.com/citycouncil")

def test_same_url_different_paths():
    assert not url_utils.same_url("https://example.com/council", "https://example.com/mayor")

def test_same_url_trailing_slash_vs_none():
    assert url_utils.same_url("https://example.com/path/", "https://example.com/path")

def test_same_url_http_vs_https():
    assert url_utils.same_url("http://www.example.com/board.htm", "https://example.com/board.htm")

def test_same_url_ignores_fragment():
    """A fragment addresses a position in a document, not another document."""
    assert url_utils.same_url("https://example.com/council#top", "https://example.com/council")

def test_same_url_ignores_differing_fragments():
    assert url_utils.same_url("https://example.com/council#a", "https://example.com/council#b")

def test_same_url_trailing_slash_before_a_fragment():
    """rstrip on the whole string could not reach a slash with a fragment after it."""
    assert url_utils.same_url("https://example.com/council/#top", "https://example.com/council")

def test_same_url_trailing_slash_before_a_query():
    assert url_utils.same_url("https://example.com/council/?x=1", "https://example.com/council?x=1")

def test_same_url_keeps_distinct_queries_apart():
    assert not url_utils.same_url("https://example.com/p?x=1", "https://example.com/p?x=2")
