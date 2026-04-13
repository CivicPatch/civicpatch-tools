import logging

import yaml

import lib.github.api as github_service
import lib.github.pr as pr_service
import shared.utils.id_utils
from database.requests import get_request_jurisdiction
from lib.github.pr import PrAuthor
from schemas.requests import ResolveIssueRequest
from shared.schemas import JurisdictionsFile
from shared.utils.config_utils import RoleConfig, RoleEntry, merge_role_configs

logger = logging.getLogger(__name__)


async def resolve_role_issue(issue: dict, body: ResolveIssueRequest, author: PrAuthor) -> tuple[str, str] | None:
    scope = body.scope or "global"
    if scope == "state":
        config_path = f"data/{body.state}/local/config.yml"
    elif scope == "locality":
        config_path = f"data/{body.state}/local/{body.locality}/config.yml"
    else:
        config_path = "data/local/config.yml"

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


async def resolve_dead_url_issue(issue: dict, new_url: str | None, comment: str | None, author: PrAuthor) -> str | None:
    jurisdiction_ocdid = await get_request_jurisdiction(issue["request_ids"][0])
    if not jurisdiction_ocdid:
        logger.error(f"No jurisdiction found for dead_url issue {issue['id']}")
        return None

    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    state = folder.split("/")[0]
    file_path = f"data_source/{state}/jurisdictions.yml"

    raw = await github_service.get_github_file_contents(file_path)
    if not raw:
        logger.error(f"Could not fetch {file_path}")
        return None

    data = JurisdictionsFile.model_validate(yaml.safe_load(raw))
    entry = next((e for e in data.jurisdictions if e.id == jurisdiction_ocdid), None)
    if not entry:
        logger.error(f"No entry for {jurisdiction_ocdid} in {file_path}")
        return None

    entry.url = new_url
    if comment:
        entry.comments.append(comment)

    content = yaml.dump(data.model_dump(mode="python", exclude_none=True), sort_keys=False, allow_unicode=True)
    pr_number, pull_request_url = await pr_service.open_attributed_pr(
        branch_name=f"resolve/url/{issue['id']}",
        file_path=file_path,
        content=content,
        commit_message=f"Fix dead URL: {jurisdiction_ocdid}",
        pull_request_title=f"Fix dead URL: {jurisdiction_ocdid}",
        pull_request_body=f"Updates URL in `{file_path}` via issue resolution.",
        author=author,
    )
    if pr_number is None:
        logger.error(f"Failed to open PR for dead URL resolution: {pull_request_url}")
        return None
    return pull_request_url
