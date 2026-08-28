"""Unit tests for the Git Data multi-file commit.

The whole value of this function is the call sequence — read the ref, read its commit, build one
tree, make one commit, move the ref — so the tests script the HTTP layer and assert on what was
sent. Nothing below reaches the network.
"""

from unittest.mock import AsyncMock, patch

import pytest

from lib.github.git_data import commit_github_files

REPO = "https://api.github.com/repos/openstates/open-data"

_REF = {"object": {"sha": "parent-sha"}}
_PARENT = {"tree": {"sha": "base-tree-sha"}}
_TREE = {"sha": "new-tree-sha"}
_COMMIT = {"sha": "new-commit-sha", "html_url": f"{REPO}/commit/new-commit-sha"}
_MOVED = {"object": {"sha": "new-commit-sha"}}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.text = str(payload)
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """Replies from a scripted queue and records what it was asked."""

    def __init__(self, replies: list[_FakeResponse]):
        self._replies = list(replies)
        self.calls: list[tuple[str, str, dict | None]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def request(self, method, url, headers=None, json=None):
        self.calls.append((method, url, json))
        return self._replies.pop(0)


def _ok(*payloads_with_status) -> _FakeClient:
    return _FakeClient(
        [_FakeResponse(status, payload) for status, payload in payloads_with_status]
    )


def _happy_path() -> _FakeClient:
    return _ok(
        (200, _REF), (200, _PARENT), (201, _TREE), (201, _COMMIT), (200, _MOVED)
    )


def _github(client: _FakeClient):
    return (
        patch(
            "lib.github.git_data._get_github_config",
            return_value=("app", "key", "install", REPO),
        ),
        patch(
            "lib.github.git_data.get_default_headers",
            new_callable=AsyncMock,
            return_value={"Authorization": "token x"},
        ),
        patch("lib.github.git_data.httpx.AsyncClient", return_value=client),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_many_files_become_one_commit():
    """Five calls whatever the file count — that is the point of this over the Contents API."""
    client = _happy_path()
    config, headers, http = _github(client)
    with config, headers, http:
        url = await commit_github_files(
            "main",
            {"data/ma/a.yml": "a: 1", "data/ma/b.yml": "b: 2"},
            "Publish 2 jurisdictions",
        )

    assert url == f"{REPO}/commit/new-commit-sha"
    assert [(method, url.rsplit("/", 2)[-2:]) for method, url, _ in client.calls] == [
        ("GET", ["heads", "main"]),
        ("GET", ["commits", "parent-sha"]),
        ("POST", ["git", "trees"]),
        ("POST", ["git", "commits"]),
        ("PATCH", ["heads", "main"]),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_tree_extends_the_parent_and_is_sorted():
    """`base_tree` is what keeps the other 3000 files in the repo; sorting keeps an unchanged
    batch producing an unchanged tree."""
    client = _happy_path()
    config, headers, http = _github(client)
    with config, headers, http:
        await commit_github_files(
            "main",
            {"data/ma/z.yml": "z: 1", "data/ma/a.yml": "a: 1"},
            "Publish",
        )

    tree_payload = client.calls[2][2]
    assert tree_payload is not None
    assert tree_payload["base_tree"] == "base-tree-sha"
    assert [entry["path"] for entry in tree_payload["tree"]] == [
        "data/ma/a.yml",
        "data/ma/z.yml",
    ]
    assert tree_payload["tree"][0] == {
        "path": "data/ma/a.yml",
        "mode": "100644",
        "type": "blob",
        "content": "a: 1",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_commit_hangs_off_the_ref_we_read():
    client = _happy_path()
    config, headers, http = _github(client)
    with config, headers, http:
        await commit_github_files("main", {"data/ma/a.yml": "a: 1"}, "Publish")

    commit_payload = client.calls[3][2]
    assert commit_payload == {
        "message": "Publish",
        "tree": "new-tree-sha",
        "parents": ["parent-sha"],
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_losing_the_ref_race_returns_none():
    """Something else committed between the read and the move. The caller re-renders and
    retries rather than forcing, so nobody's commit is discarded."""
    client = _ok(
        (200, _REF),
        (200, _PARENT),
        (201, _TREE),
        (201, _COMMIT),
        (422, {"message": "Update is not a fast forward"}),
    )
    config, headers, http = _github(client)
    with config, headers, http:
        url = await commit_github_files("main", {"data/ma/a.yml": "a: 1"}, "Publish")

    assert url is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_nothing_to_write_touches_github_at_all():
    """A batch where every jurisdiction failed must not leave an empty commit."""
    client = _happy_path()
    config, headers, http = _github(client)
    with config, headers, http:
        url = await commit_github_files("main", {}, "Publish")

    assert url is None
    assert client.calls == []
