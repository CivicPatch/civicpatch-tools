"""What syncing one open-data config file changes: its roles in `roles` and `role_aliases`, and
its government government forms for the activity row. Pure.

Roles are matched by id, not label (unlike `role_taxonomy`, which serves the editor): the file
carries ids, so a new label on a known id is a rename. A role the file used to define and no
longer lists is deactivated, never deleted, since posts may still point at it.
"""

from pydantic import BaseModel

from core.role_taxonomy import RoleOp, diff_aliases
from shared.schemas import Role, RoleStatus
from shared.utils.layered_config import COUNTRY_ROLES_PATH, ConfigRole, GovernmentFormsConfig


class StoredRole(Role):
    config_path: str | None = None


class RoleUpsert(BaseModel):
    op: RoleOp
    role: ConfigRole
    priority: int | None
    aliases_added: set[str] = set()
    aliases_removed: set[str] = set()


class RoleChanges(BaseModel):
    upserts: list[RoleUpsert]
    deactivations: list[StoredRole]


def role_priority(path: str, position: int) -> int | None:
    """Country roles rank in file order; a state's roles rank after them, unranked."""
    return position if path == COUNTRY_ROLES_PATH else None


def role_changes(path: str, file_roles: list[ConfigRole], stored: list[StoredRole]) -> RoleChanges:
    stored_by_id = {role.id: role for role in stored}
    upserts = []
    for position, role in enumerate(file_roles):
        upsert = _upsert(path, role, role_priority(path, position), stored_by_id.get(role.id))
        if upsert is not None:
            upserts.append(upsert)
    listed = {role.id for role in file_roles}
    deactivations = [
        role
        for role in stored
        if role.config_path == path and role.id not in listed and role.status != RoleStatus.INACTIVE
    ]
    return RoleChanges(upserts=upserts, deactivations=deactivations)


def _upsert(path: str, role: ConfigRole, priority: int | None, stored: StoredRole | None) -> RoleUpsert | None:
    if stored is None:
        return RoleUpsert(op=RoleOp.ADD, role=role, priority=priority, aliases_added=set(role.aliases))
    added, removed = diff_aliases(stored.aliases, role.aliases)
    op = RoleOp.EDIT if _fields_changed(path, role, stored) else RoleOp.NO_CHANGE
    if op is RoleOp.NO_CHANGE and not added and not removed and stored.priority == priority:
        return None
    return RoleUpsert(op=op, role=role, priority=priority, aliases_added=added, aliases_removed=removed)


def _fields_changed(path: str, role: ConfigRole, stored: StoredRole) -> bool:
    return (
        role.label != stored.label
        or role.is_unique != bool(stored.is_unique)
        or stored.status != RoleStatus.ACTIVE
        or stored.config_path != path
    )


class GovernmentFormChanges(BaseModel):
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []


def government_form_changes(before: GovernmentFormsConfig, after: GovernmentFormsConfig) -> GovernmentFormChanges:
    return GovernmentFormChanges(
        added=sorted(government_form.value for government_form in after if government_form not in before),
        removed=sorted(government_form.value for government_form in before if government_form not in after),
        changed=sorted(government_form.value for government_form in after if government_form in before and after[government_form] != before[government_form]),
    )
