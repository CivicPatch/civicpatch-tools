import base64
from unittest.mock import AsyncMock, patch

import pytest

from lib.github.api import GithubUnavailableError, RepoTree, _matches, get_tree

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


# ── _matches: skipping a write that would change nothing ─────────────────────
#
# Pure, so no mocks. It decides whether `upsert_github_file` sends a PUT at all — and it is the
# only thing between the sync sweep and a commit per scrape, since a scrape that re-confirms a
# roster renders a byte-identical file.


def _github_get(content: str, encoding: str = "base64") -> dict:
    """A contents-API response, wrapped at 60 characters the way GitHub sends it."""
    raw = base64.b64encode(content.encode()).decode()
    wrapped = "\n".join(raw[i : i + 60] for i in range(0, len(raw), 60)) + "\n"
    return {"sha": "abc123", "encoding": encoding, "content": wrapped}


def _encoded(content: str) -> str:
    """What `upsert_github_file` builds to send — unwrapped."""
    return base64.b64encode(content.encode()).decode()


@pytest.mark.unit
def test_identical_content_matches_through_githubs_line_wrapping():
    """The one case the whole thing exists for. GitHub wraps at 60 characters and we do not, so
    a naive equality would never match and every write would be a write."""
    roster = "- id: p1\n  name: Ada Chen\n  roles:\n  - name: Mayor\n" * 8
    assert _matches(_github_get(roster), _encoded(roster)) is True


@pytest.mark.unit
def test_a_single_byte_of_difference_does_not_match():
    assert _matches(_github_get("name: Ada Chen\n"), _encoded("name: Ada Chin\n")) is False


@pytest.mark.unit
def test_a_file_too_large_to_inline_is_written_anyway():
    """GitHub returns `encoding: "none"` and no content past 1 MB. Unknown means write — a
    redundant commit is cheap and a skipped real one is not."""
    existing = {"sha": "abc123", "encoding": "none", "content": ""}
    assert _matches(existing, _encoded("anything")) is False


@pytest.mark.unit
def test_a_response_without_content_is_written_anyway():
    assert _matches({"sha": "abc123", "encoding": "base64"}, _encoded("x")) is False
