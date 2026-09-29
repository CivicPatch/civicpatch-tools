"""Queries for open-data's config files: the stored copy of each, and applying its roles.

The decisions live in `core.jurisdiction_config_sync`; this module owns the SQL and the
transaction around one file.
"""

import json

from core.jurisdiction_config_sync import RoleChanges, StoredRole, form_changes, role_changes
from core.role_taxonomy import RoleOp, build_event_payload, change_log_type
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.jurisdiction_configs import JurisdictionConfigVersion
from shared.schemas import RoleAliasStatus, RoleStatus
from shared.utils.layered_config import ConfigFile, ConfigRole
from shared.utils.statuses import ActivityType


async def sync_jurisdiction_config(version: JurisdictionConfigVersion, config: ConfigFile) -> None:
    """Store one config file and apply its roles, in one transaction."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await sync_jurisdiction_config_on(cur, version, config)
        await conn.commit()


async def get_jurisdiction_configs() -> dict[str, ConfigFile]:
    """Every stored config file by its open-data path: a few dozen rows, read whole."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT path, content FROM jurisdiction_configs")
        return {path: ConfigFile.model_validate(content) for path, content in await cur.fetchall()}


async def sync_jurisdiction_config_on(cur, version: JurisdictionConfigVersion, config: ConfigFile) -> None:
    """The same, inside a caller's transaction: the dev seed applies files beside its own writes."""
    changes = role_changes(version.path, config.roles, await _stored_roles(cur))
    await _apply_role_changes(cur, changes, version)
    before = await _stored_config(cur, version.path)
    await _save_config(cur, version, config)
    forms = form_changes(before.government_forms, config.government_forms)
    await _emit(
        cur, ActivityType.SYNC_JURISDICTION_CONFIG, {**version.model_dump(), "forms": forms.model_dump()}
    )


async def _stored_roles(cur) -> list[StoredRole]:
    await cur.execute(
        """
        SELECT r.id, r.label, r.status, r.is_unique, r.priority, r.config_path,
               COALESCE(
                   array_agg(a.label ORDER BY a.label) FILTER (WHERE a.id IS NOT NULL),
                   '{}'
               )
        FROM roles r
        LEFT JOIN role_aliases a ON a.role_id = r.id AND a.status = %s
        GROUP BY r.id
        """,
        (RoleAliasStatus.ACTIVE,),
    )
    return [
        StoredRole(
            id=id,
            label=label,
            status=status,
            is_unique=is_unique,
            priority=priority,
            config_path=config_path,
            aliases=aliases,
        )
        for id, label, status, is_unique, priority, config_path, aliases in await cur.fetchall()
    ]


async def _stored_config(cur, path: str) -> ConfigFile:
    await cur.execute("SELECT content FROM jurisdiction_configs WHERE path = %s", (path,))
    row = await cur.fetchone()
    return ConfigFile.model_validate(row[0]) if row else ConfigFile()


async def _save_config(cur, version: JurisdictionConfigVersion, config: ConfigFile) -> None:
    await cur.execute(
        """
        INSERT INTO jurisdiction_configs (path, content, commit_sha)
        VALUES (%s, %s, %s)
        ON CONFLICT (path) DO UPDATE
            SET content = EXCLUDED.content, commit_sha = EXCLUDED.commit_sha, synced_at = now()
        """,
        (version.path, config.model_dump_json(), version.commit_sha),
    )


async def _apply_role_changes(cur, changes: RoleChanges, version: JurisdictionConfigVersion) -> None:
    # Every removal first, so an alias moving between two roles in one file never collides.
    for upsert in changes.upserts:
        for alias in upsert.aliases_removed:
            await cur.execute(
                "DELETE FROM role_aliases WHERE role_id = %s AND lower(label) = lower(%s)",
                (upsert.role.id, alias),
            )
    for upsert in changes.upserts:
        await _write_role(cur, version.path, upsert.op, upsert.role, upsert.priority)
        for alias in sorted(upsert.aliases_added):
            await cur.execute(
                "INSERT INTO role_aliases (role_id, label, status) VALUES (%s, %s, %s)",
                (upsert.role.id, alias, RoleAliasStatus.ACTIVE),
            )
        if upsert.op is not RoleOp.NO_CHANGE or upsert.aliases_added or upsert.aliases_removed:
            payload = build_event_payload(upsert.role.label, upsert.aliases_added, upsert.aliases_removed)
            await _emit(cur, change_log_type(upsert.op), {**payload, **version.model_dump()})
    for role in changes.deactivations:
        await cur.execute("UPDATE roles SET status = %s WHERE id = %s", (RoleStatus.INACTIVE, role.id))
        await _emit(cur, ActivityType.DELETE_ROLE, {"role": role.label, **version.model_dump()})


async def _write_role(cur, path: str, op: RoleOp, role: ConfigRole, priority: int | None) -> None:
    if op is RoleOp.ADD:
        await cur.execute(
            """
            INSERT INTO roles (id, label, status, is_unique, priority, config_path)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (role.id, role.label, RoleStatus.ACTIVE, role.is_unique, priority, path),
        )
        return
    await cur.execute(
        """
        UPDATE roles SET label = %s, status = %s, is_unique = %s, priority = %s, config_path = %s
        WHERE id = %s
        """,
        (role.label, RoleStatus.ACTIVE, role.is_unique, priority, path, role.id),
    )


async def _emit(cur, activity_type: str, payload: dict) -> None:
    await cur.execute(
        "INSERT INTO activity (type, jurisdiction_ocdid, changes, user_id) VALUES (%s, NULL, %s, %s)",
        (activity_type, json.dumps(payload), SYSTEM_USER_ID),
    )
