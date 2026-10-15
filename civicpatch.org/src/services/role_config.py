import logging

import database.roles as db_roles
from shared.schemas import Role

logger = logging.getLogger(__name__)


async def load_roles() -> list[Role]:
    return await db_roles.get_roles()
