"""A Role Taxonomy edit, as a pull request against open-data's country config file."""

import environment
import lib.github.api as github_service
import shared.utils.id_utils as id_utils
from lib.github.auth import get_default_headers
from lib.github.pull_requests import PrAuthor, open_attributed_pr
from pydantic import BaseModel
from shared.utils.layered_config import COUNTRY_ROLES_PATH
from shared.utils.statuses import PullRequestLabel

import database.users as users_db
from core.role_config_edits import RoleConfigEditRefused, RolesEdit, edited_config_text

BRANCH_PREFIX = "civicpatch/role-config/"


class RoleConfigPullRequestAlreadyOpen(Exception):
    def __init__(self, url: str):
        super().__init__(url)
        self.url = url


class RoleConfigPullRequestFailed(Exception):
    pass


class OpenedRoleConfigPullRequest(BaseModel):
    pull_request_number: int
    pull_request_url: str


async def open_role_config_pull_request(
    edit: RolesEdit, summary: str, label: PullRequestLabel, user_id: str
) -> OpenedRoleConfigPullRequest:
    repo_url = environment.get_env_vars()["OPEN_DATA_REPO_URL"]
    headers = await get_default_headers()
    await _refuse_if_one_is_open(repo_url, headers)
    content = await _edited_config(repo_url, edit)
    number, url_or_error = await open_attributed_pr(
        branch_name=f"{BRANCH_PREFIX}{id_utils.make_id()}",
        file_path=COUNTRY_ROLES_PATH,
        content=content,
        commit_message=f"Roles: {summary}",
        pull_request_title=f"Roles: {summary}",
        pull_request_body=summary,
        author=await _author(user_id),
        labels=(label,),
        repo_url=repo_url,
        headers=headers,
        # No fork: the regular bot writes and labels open-data itself.
        fork_repo_url=repo_url,
        fork_headers=headers,
    )
    if number is None:
        raise RoleConfigPullRequestFailed(url_or_error)
    return OpenedRoleConfigPullRequest(pull_request_number=number, pull_request_url=url_or_error)


async def _refuse_if_one_is_open(repo_url: str, headers: dict) -> None:
    """One at a time: two edits of one file would conflict at merge."""
    for pull_request in await github_service.list_open_pull_requests(repo_url, headers):
        if pull_request.branch.startswith(BRANCH_PREFIX):
            raise RoleConfigPullRequestAlreadyOpen(pull_request.url)


async def _edited_config(repo_url: str, edit: RolesEdit) -> str:
    raw = await github_service.get_github_file_contents(COUNTRY_ROLES_PATH, ref="main", repo_url=repo_url)
    if not raw:
        raise RoleConfigPullRequestFailed(f"Could not read {COUNTRY_ROLES_PATH}")
    content = edited_config_text(raw, edit)
    if content == raw:
        raise RoleConfigEditRefused("Nothing to change.")
    return content


async def _author(user_id: str) -> PrAuthor:
    user = await users_db.get_user_by_id(user_id)
    if user is None:
        raise RoleConfigPullRequestFailed(f"No user {user_id} to author the pull request")
    return PrAuthor(name=user["username"] or user["email"], email=user["email"])
