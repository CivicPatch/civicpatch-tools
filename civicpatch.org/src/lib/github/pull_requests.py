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
    base: str = "main",
    repo_url: str | None = None,
    fork_repo_url: str | None = None,
    headers: dict | None = None,
    fork_headers: dict | None = None,
) -> tuple[int, str] | tuple[None, str]:
    """Creates a branch, commits a file, and opens a PR. Returns (pr_number, pr_url) or (None, error)."""
    branch_repo_url = fork_repo_url or repo_url
    effective_fork_headers = fork_headers or headers

    if fork_repo_url:
        if err := await github_api_service.sync_fork_branch(branch=base, repo_url=fork_repo_url, headers=effective_fork_headers):
            return None, f"Failed to sync fork: {err}"

    if err := await github_api_service.create_branch(branch_name, base_ref=base, repo_url=branch_repo_url, headers=effective_fork_headers):
        return None, f"Failed to create branch: {err}"

    if not await github_api_service.upsert_github_file(
        branch_name,
        file_path,
        content,
        commit_message,
        author={"name": author.name, "email": author.email},
        repo_url=branch_repo_url,
        headers=effective_fork_headers,
    ):
        return None, "Failed to write file to branch"

    # Cross-repo PRs require head in "fork_org:branch_name" format
    pr_head = None
    if fork_repo_url:
        fork_org = fork_repo_url.rstrip("/").split("/")[-2]
        pr_head = f"{fork_org}:{branch_name}"

    attributed_body = (
        f"{pull_request_body}\n\n---\n_Opened by {author.name} ({author.email}) via CivicPatch._"
    )
    labels = [f"team:{t}" for t in author.teams] or None
    return await github_api_service.create_pull_request(
        branch_name,
        title=pull_request_title,
        body=attributed_body,
        base=base,
        repo_url=repo_url,
        headers=headers,
        head=pr_head,
        labels=labels,
    )
