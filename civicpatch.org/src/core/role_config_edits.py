from collections.abc import Callable

from schemas.roles import RoleInput
from shared.utils.layered_config import ConfigFile, ConfigRole
from shared.utils.yaml_utils import yaml_dump, yaml_load

from core.role_taxonomy import slugify_label

RolesEdit = Callable[[list[ConfigRole]], list[ConfigRole]]


class RoleConfigEditRefused(Exception):
    pass


def with_role_added(roles: list[ConfigRole], role: RoleInput) -> list[ConfigRole]:
    added = ConfigRole(
        id=slugify_label(role.label),
        label=role.label,
        is_unique=role.is_unique,
        aliases=role.aliases,
    )
    return _checked([*roles, added])


def with_role_edited(
    roles: list[ConfigRole], role_id: str, role: RoleInput
) -> list[ConfigRole]:
    """The id stays, so a renamed role keeps its posts."""
    edit = {
        "label": role.label,
        "is_unique": role.is_unique,
        "aliases": list(role.aliases),
    }
    return _checked(
        [
            listed.model_copy(update=edit) if listed.id == role_id else listed
            for listed in roles
        ]
    )


def without_role(roles: list[ConfigRole], role_id: str) -> list[ConfigRole]:
    return _checked([listed for listed in roles if listed.id != role_id])


def with_role_order(roles: list[ConfigRole], role_order: list[str]) -> list[ConfigRole]:
    """Ids the file does not list (the database's own, like `unmatched`) are ignored."""
    unplaced = [listed.id for listed in roles if listed.id not in role_order]
    if unplaced:
        raise RoleConfigEditRefused(f"the new order leaves out {', '.join(unplaced)}")
    return _checked(sorted(roles, key=lambda listed: role_order.index(listed.id)))


def edited_config_text(raw: str, edit: RolesEdit) -> str:
    """Only `roles:` is rewritten; the rest of the file keeps its text."""
    document = yaml_load(raw)
    roles = ConfigFile.model_validate(document).roles
    document["roles"] = [role.model_dump() for role in edit(roles)]
    return yaml_dump(document)


def _checked(roles: list[ConfigRole]) -> list[ConfigRole]:
    try:
        ConfigFile(roles=roles)
    except ValueError as error:
        raise RoleConfigEditRefused(str(error)) from error
    return roles
