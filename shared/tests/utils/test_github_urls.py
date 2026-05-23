import pytest
from shared.utils import github_urls


API_URL = "https://api.github.com/repos/CivicPatch/open-data"


def test_derive_git_clone_url():
    assert github_urls.derive_git_clone_url(API_URL) == "https://github.com/CivicPatch/open-data.git"


def test_derive_git_clone_url_strips_trailing_slash():
    assert github_urls.derive_git_clone_url(API_URL + "/") == "https://github.com/CivicPatch/open-data.git"


def test_derive_raw_base_url_default_main():
    assert (
        github_urls.derive_raw_base_url(API_URL)
        == "https://raw.githubusercontent.com/CivicPatch/open-data/refs/heads/main"
    )


def test_derive_raw_base_url_custom_ref():
    assert (
        github_urls.derive_raw_base_url(API_URL, ref="refs/heads/development")
        == "https://raw.githubusercontent.com/CivicPatch/open-data/refs/heads/development"
    )


def test_derive_raw_base_url_works_with_test_repo():
    assert (
        github_urls.derive_raw_base_url("https://api.github.com/repos/CivicPatch/test-open-data")
        == "https://raw.githubusercontent.com/CivicPatch/test-open-data/refs/heads/main"
    )


def test_rejects_non_api_url():
    with pytest.raises(ValueError, match="Expected a GitHub API URL"):
        github_urls.derive_git_clone_url("https://github.com/CivicPatch/open-data")


def test_rejects_empty_string():
    with pytest.raises(ValueError):
        github_urls.derive_raw_base_url("")
