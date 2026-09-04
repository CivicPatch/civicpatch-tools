"""Many files in one commit, via GitHub's Git Data API.

The Contents API that `api.upsert_github_file` uses writes one blob per commit, so publishing
forty jurisdictions leaves forty commits. This builds a tree instead: five calls regardless of
how many files, and one commit at the end.

Write-only, and now the only writer: nothing in the codebase deletes from open-data. The
delete this used to point at removed an unreviewed file that had not been written for many
migrations, and it went with `promote_to_reviewed`.
"""

import logging

import httpx

from lib.github.api import timeout
from lib.github.auth import _get_github_config, get_default_headers

logger = logging.getLogger(__name__)

_BLOB_MODE = "100644"


def _tree_entries(contents: dict[str, str]) -> list[dict]:
    """Sorted so the same batch produces the same tree — git hashes entry order."""
    return [
        {"path": path, "mode": _BLOB_MODE, "type": "blob", "content": content}
        for path, content in sorted(contents.items())
    ]


async def _call(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    expect: int,
    json: dict | None = None,
) -> dict | None:
    response = await client.request(method, url, headers=headers, json=json)
    if response.status_code != expect:
        logger.error(
            f"commit_github_files: {method} {url} failed "
            f"({response.status_code}): {response.text}"
        )
        return None
    return response.json()


async def commit_github_files(
    branch_name: str,
    contents: dict[str, str],
    commit_message: str,
    repo_url: str | None = None,
    headers: dict | None = None,
) -> str | None:
    """Write every path in `contents` as a single commit. Returns its URL, or None if rejected.

    The ref move is a fast-forward, so a commit landing on the branch between the read and the
    move loses the race and returns None. That is the correct outcome: the caller re-renders
    from the database and retries, which is cheaper and safer than merging trees here.
    """
    if not contents:
        return None

    _, _, _, open_data_repo_url = _get_github_config()
    repo = repo_url or open_data_repo_url
    auth = headers if headers is not None else await get_default_headers()

    async with httpx.AsyncClient(timeout=timeout) as client:
        ref = await _call(client, "GET", f"{repo}/git/ref/heads/{branch_name}", auth, 200)
        if ref is None:
            return None
        parent_sha = ref["object"]["sha"]

        parent = await _call(client, "GET", f"{repo}/git/commits/{parent_sha}", auth, 200)
        if parent is None:
            return None

        tree = await _call(
            client,
            "POST",
            f"{repo}/git/trees",
            auth,
            201,
            {"base_tree": parent["tree"]["sha"], "tree": _tree_entries(contents)},
        )
        if tree is None:
            return None

        commit = await _call(
            client,
            "POST",
            f"{repo}/git/commits",
            auth,
            201,
            {
                "message": commit_message,
                "tree": tree["sha"],
                "parents": [parent_sha],
            },
        )
        if commit is None:
            return None

        moved = await _call(
            client,
            "PATCH",
            f"{repo}/git/refs/heads/{branch_name}",
            auth,
            200,
            {"sha": commit["sha"]},
        )
        return commit["html_url"] if moved else None
