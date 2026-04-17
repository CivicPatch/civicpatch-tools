import logging

import yaml

import lib.github.api as github_service
import lib.github.pr as pr_service
from lib.github.pr import PrAuthor
from schemas.pipeline_runs import ResolveIssueRequest
from shared.utils.config_utils import RoleConfig, RoleEntry, merge_role_configs

logger = logging.getLogger(__name__)


async def resolve_role_issue(issue: dict, body: ResolveIssueRequest, author: PrAuthor) -> tuple[str, str] | None:
    scope = body.scope or "global"
    if scope == "state":
        config_path = f"data_source/{body.state}/local/config.yml"
    elif scope == "locality":
        config_path = f"data_source/{body.state}/local/{body.locality}/config.yml"
    else:
        config_path = "data_source/local/config.yml"

    raw = await github_service.get_github_file_contents(config_path)
    existing = RoleConfig.model_validate(yaml.safe_load(raw)) if raw else RoleConfig()
    merged = merge_role_configs(existing, RoleConfig(roles=[RoleEntry(role=issue["issue_key"])]))
    content = yaml.dump(merged.model_dump(), sort_keys=False, allow_unicode=True)

    pr_number, pull_request_url = await pr_service.open_attributed_pr(
        branch_name=f"resolve/role/{issue['id']}",
        file_path=config_path,
        content=content,
        commit_message=f"Add role: {issue['issue_key']}",
        pull_request_title=f"Add unrecognized role: {issue['issue_key']}",
        pull_request_body=f"Adds `{issue['issue_key']}` to `{config_path}` via issue resolution.",
        author=author,
    )
    if pr_number is None:
        logger.error(f"Failed to open PR for role resolution: {pull_request_url}")
        return None
    return pull_request_url, config_path


