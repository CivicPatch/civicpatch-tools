import logging

import core.role_config as role_config_service
from database.issues import resolve_issue
from schemas.jurisdictions import SetScopeRolesRequest

logger = logging.getLogger(__name__)


async def resolve_via_config_db(req: SetScopeRolesRequest, user_id: str | None, issue_id: str) -> None:
    """Write role config changes to the DB and mark the issue as resolved."""
    await role_config_service.set_scope_roles(req, user_id=user_id)
    await resolve_issue(issue_id)
    logger.info("Resolved issue %s via DB role config update for %s", issue_id, req.ocdid)