import logging

import services.role_config as role_config_service
from database.issues import resolve_issue
from schemas.roles import RoleInput

logger = logging.getLogger(__name__)


async def resolve_via_config_db(
    roles: list[RoleInput], user_id: str | None, issue_id: str
) -> None:
    """Write role config changes to the DB and mark the issue as resolved."""
    await role_config_service.set_roles(roles, user_id=user_id)
    await resolve_issue(issue_id)
    logger.info("Resolved issue %s via DB role config update", issue_id)
