import logging

from pydantic import BaseModel

import lib.github.api as github_api_service

logger = logging.getLogger(__name__)


class PrAuthor(BaseModel):
    name: str
    email: str
    teams: list[str] = []


async def open_attributed_pr(
    *,
    branch_name: str,
    file_path: str,
    content: str,
    commit_message: str,
    pull_request_title: str,
    pull_request_body: str,
    author: PrAuthor,
    labels: tuple[str, ...],
    repo_url: str,
    headers: dict,
    fork_repo_url: str,
    fork_headers: dict,
    base: str = "main",
) -> tuple[int, str] | tuple[None, str]:
    """Commits a file to a new branch in the fork and opens a PR from it on the repo.

    Two bots: `fork_headers` writes the fork (branch, commit), `headers` opens and labels the PR,
    so the one that labels needs no write access to the repo's contents. The branch starts at the
    repo's `base`, not the fork's, so a fork behind its parent never leaks old commits into the PR.
    Returns (pr_number, pr_url) or (None, error).
    """
    if err := await github_api_service.create_branch(
        branch_name, base_ref=base, repo_url=fork_repo_url, headers=fork_headers, base_repo_url=repo_url
    ):
        return None, f"Failed to create branch: {err}"

    if not await github_api_service.upsert_github_file(
        branch_name,
        file_path,
        content,
        commit_message,
        author={"name": author.name, "email": author.email},
        repo_url=fork_repo_url,
        headers=fork_headers,
    ):
        return None, "Failed to write file to branch"

    attributed_body = f"{pull_request_body}\n\n---\n_Opened by {author.name} ({author.email}) via CivicPatch._"
    all_labels = [*labels, *(f"team:{t}" for t in author.teams)] or None
    fork_owner, fork_name = repo_owner_and_name(fork_repo_url)
    return await github_api_service.create_pull_request(
        f"{fork_owner}:{branch_name}",
        title=pull_request_title,
        body=attributed_body,
        base=base,
        repo_url=repo_url,
        headers=headers,
        labels=all_labels,
        head_repo=f"{fork_owner}/{fork_name}",
    )


def repo_owner_and_name(repo_url: str) -> tuple[str, str]:
    """The last two path segments of a repo's API url: its owner and its name."""
    owner, name = repo_url.rstrip("/").split("/")[-2:]
    return owner, name
