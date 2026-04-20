import logging

import yaml

import lib.github.api as github_service
import lib.github.pull_requests as pr_service
from lib.github.pull_requests import PrAuthor
from schemas.pipeline_runs import ResolveIssueRequest
from shared.utils import id_utils
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


async def resolve_domain_inactive_fixed(issue: dict, author: PrAuthor) -> tuple[str, str] | None:
    data = issue.get("data") or {}
    jurisdiction_ocdid = (issue.get("jurisdictions") or [{}])[0].get("jurisdiction_ocdid")
    discovered_url = data.get("discovered_url")

    if not jurisdiction_ocdid or not discovered_url:
        logger.error("resolve_domain_inactive_fixed: missing jurisdiction_ocdid or discovered_url")
        return None

    ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    state = ocdid_parts.state
    config_path = f"data_source/{state}/jurisdictions.yml"

    raw = await github_service.get_github_file_contents(config_path)
    if raw is None:
        logger.error(f"resolve_domain_inactive_fixed: could not fetch {config_path}")
        return None

    data_yml = yaml.safe_load(raw)
    entries = data_yml.get("jurisdictions", [])
    updated = False
    for entry in entries:
        if entry.get("id") == jurisdiction_ocdid:
            entry["url"] = discovered_url
            updated = True
            break

    if not updated:
        logger.error(f"resolve_domain_inactive_fixed: jurisdiction {jurisdiction_ocdid} not found in {config_path}")
        return None

    content = yaml.dump(data_yml, sort_keys=False, allow_unicode=True)

    pr_number, pull_request_url = await pr_service.open_attributed_pr(
        branch_name=f"resolve/domain-inactive/{issue['id']}",
        file_path=config_path,
        content=content,
        commit_message=f"Update URL for {jurisdiction_ocdid}",
        pull_request_title=f"Fix inactive domain: {data.get('original_url', jurisdiction_ocdid)}",
        pull_request_body=(
            f"Updates the URL for `{jurisdiction_ocdid}` from `{data.get('original_url')}` "
            f"to `{discovered_url}` (discovered via Gemini URL search)."
        ),
        author=author,
    )
    if pr_number is None:
        logger.error(f"resolve_domain_inactive_fixed: failed to open PR: {pull_request_url}")
        return None
    return pull_request_url, config_path


