from database.jurisdiction_configs import get_jurisdiction_configs
from shared.schemas import JurisdictionLevel, Role
from shared.utils.layered_config import every_role, layer_roles


async def load_roles(level: JurisdictionLevel | None, state: str | None) -> list[Role]:
    """Every level's and state's roles; or one level's, with one state's added when named."""
    configs = await get_jurisdiction_configs()
    if level is None:
        return every_role(configs)
    return layer_roles(configs, level, state)
