import logging

import core.role_config as role_config_service
import lib.github.pull_requests as pr_service
from database.issues import open_issue_pull_request
from lib.github.pull_requests import PrAuthor
from schemas.jurisdictions import SetScopeRolesRequest
from shared.utils.id_utils import jurisdiction_ocdid_to_folder

logger = logging.getLogger(__name__)


async def resolve_via_config_pr(req: SetScopeRolesRequest, author: PrAuthor, issue_id: str) -> str:
    folder = jurisdiction_ocdid_to_folder(req.ocdid)
    path, content = await role_config_service.build_updated_config(req)
    branch_name = f"config/{req.scope}/{req.ocdid.replace('/', '-')}"
    pr_number, pull_request_url = await pr_service.open_attributed_pr(
        branch_name=branch_name,
        file_path=path,
        content=content,
        commit_message=f"Update {req.scope} roles for {folder}",
        pull_request_title=f"Update {req.scope} role config: {folder}",
        pull_request_body=f"Updates role config at `{path}`.",
        author=author,
    )
    if pr_number is None:
        raise RuntimeError(f"Failed to open config PR: {pull_request_url}")
    await open_issue_pull_request(issue_id, pull_request_url)
    return pull_request_url
