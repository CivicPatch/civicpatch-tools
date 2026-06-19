from unittest.mock import AsyncMock, patch

import pytest

from lib.github.api import GithubUnavailableError, RepoTree, get_tree

REPO_URL = "https://api.github.com/repos/openstates/open-data"

# A tree response with one file (blob), one directory (tree), and one submodule (commit).
_TREE_RESPONSE = {
    "sha": "root-sha",
    "truncated": False,
    "tree": [
        {"path": "data/tx/local/place_austin.yml", "type": "blob", "sha": "sha-austin"},
        {"path": "data/tx/local", "type": "tree", "sha": "sha-dir"},
        {"path": "vendor/submodule", "type": "commit", "sha": "sha-sub"},
        {"path": "data_source/tx/local/jurisdictions.yml", "type": "blob", "sha": "sha-juris"},
    ],
}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_tree_keeps_only_blobs_as_path_to_sha():
    with patch(
        "lib.github.api.cached_github_get",
        new_callable=AsyncMock,
        return_value=_TREE_RESPONSE,
    ):
        tree = await get_tree(REPO_URL)

    assert isinstance(tree, RepoTree)
    assert tree.entries == {
        "data/tx/local/place_austin.yml": "sha-austin",
        "data_source/tx/local/jurisdictions.yml": "sha-juris",
    }
    # directory ("tree") and submodule ("commit") entries are dropped
    assert "data/tx/local" not in tree.entries
    assert "vendor/submodule" not in tree.entries


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_tree_surfaces_truncated():
    truncated_response = {**_TREE_RESPONSE, "truncated": True}
    with patch(
        "lib.github.api.cached_github_get",
        new_callable=AsyncMock,
        return_value=truncated_response,
    ):
        tree = await get_tree(REPO_URL)

    assert tree.truncated is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_tree_raises_when_fetch_returns_none():
    # cached_github_get returns None for a 404 and (under the minimal seam) any other
    # non-200 it can't use. For the tree of `main` that's an anomaly, so get_tree raises
    # rather than proceed on a tree it couldn't read — this is what keeps a transient blip
    # from looking like an empty tree (which would mass-delete downstream).
    with patch(
        "lib.github.api.cached_github_get",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(GithubUnavailableError):
            await get_tree(REPO_URL)
