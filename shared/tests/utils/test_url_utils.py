import pytest
from shared.utils import url_utils


# format_url

def test_format_url_adds_scheme():
    assert url_utils.format_url("example.com") == "https://example.com"

def test_format_url_lowercases_scheme():
    assert url_utils.format_url("HTTPS://example.com/Path").startswith("https://")

def test_format_url_lowercases_host():
    assert url_utils.format_url("https://EXAMPLE.COM/Path") == "https://example.com/Path"

def test_format_url_preserves_path_case():
    assert url_utils.format_url("https://example.com/CityCouncil") == "https://example.com/CityCouncil"

def test_format_url_strips_trailing_slash():
    assert url_utils.format_url("https://example.com/path/") == "https://example.com/path"

def test_format_url_preserves_www():
    assert url_utils.format_url("https://www.example.com/path") == "https://www.example.com/path"


# normalize_url (for comparison only)

def test_normalize_url_strips_www():
    assert url_utils.normalize_url("https://www.example.com") == url_utils.normalize_url("https://example.com")

def test_normalize_url_lowercases_path():
    assert url_utils.normalize_url("https://example.com/CityCouncil") == url_utils.normalize_url("https://example.com/citycouncil")


# same_url

def test_same_url_www_vs_non_www():
    assert url_utils.same_url("https://www.example.com/path", "https://example.com/path")

def test_same_url_path_case_insensitive():
    assert url_utils.same_url("https://example.com/CityCouncil", "https://example.com/citycouncil")

def test_same_url_different_paths():
    assert not url_utils.same_url("https://example.com/council", "https://example.com/mayor")
