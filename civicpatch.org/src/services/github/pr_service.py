import logging

from pydantic import BaseModel

import services.github.github_api_service as github_api_service

logger = logging.getLogger(__name__)


class PrAuthor(BaseModel):
    name: str
    email: str


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
) -> tuple[int, str] | tuple[None, str]:
    """
    Creates a branch, commits a file with author attribution, and opens a PR.
    Returns (pull_request_number, pull_request_url) on success or (None, error_message).
    """
    if err := await github_api_service.create_branch(branch_name, base_ref=base):
        return None, f"Failed to create branch: {err}"

    if not await github_api_service.upsert_github_file(
        branch_name,
        file_path,
        content,
        commit_message,
        author={"name": author.name, "email": author.email},
    ):
        return None, "Failed to write file to branch"

    attributed_body = (
        f"{pull_request_body}\n\n---\n_Opened by {author.name} ({author.email}) via CivicPatch._"
    )
    return await github_api_service.create_pull_request(
        branch_name,
        title=pull_request_title,
        body=attributed_body,
        base=base,
    )
