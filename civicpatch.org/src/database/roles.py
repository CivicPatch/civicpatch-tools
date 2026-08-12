"""Database queries for the role taxonomy (roles).

roles holds what each scope says about a role — its label, status,
uniqueness, priority, and aliases as a text[] array. `label` is the identity;
no separate `roles` table.

Inheritance lives in the data model: NULL on a scoped roles field
means "inherit from the broader scope". Resolution folds per-field in
core/role_resolution.py (pending).
"""

import json
from enum import Enum

from database.database import get_pool
from shared.schemas import Role, RoleConfig


class TermOp(str, Enum):
    ADD = "add"  # insert a new role_entry row
    EDIT = "edit"  # UPDATE existing entry's tracked fields (label, status, is_unique, priority)
    # NO_CHANGE: entry row stays as-is. Common case — the PUT sent the same
    # values for all tracked fields. The shell still updates the aliases array
    # for this entry because the incoming `aliases:` list can differ from what's
    # currently in roles.aliases.
    NO_CHANGE = "no_change"


def _state_ocdid_from_ocdid(ocdid: str) -> str | None:
    """Derive the state-level OCDID for a given place OCDID. Must produce the
    same form as services.role_config._scope_to_ocdid("state", ...) so the keys
    match across writes/reads."""
    parts = ocdid.split("/")
    for i, p in enumerate(parts):
        if p.startswith("state:"):
            return "/".join(parts[: i + 1] + [parts[-1]])
    return None


async def _fetch_roles_at_scope(cur, scope: str | None) -> list[Role]:
    """Fetch all roles at a single scope."""
    await cur.execute(
        """
        SELECT label, status, is_unique, priority, aliases
        FROM roles
        WHERE scope IS NOT DISTINCT FROM %s
        ORDER BY priority NULLS LAST, label
        """,
        (scope,),
    )
    return [
        Role(label=label, status=status, is_unique=is_unique, priority=priority, aliases=aliases)
        for label, status, is_unique, priority, aliases in await cur.fetchall()
    ]


async def get_role_config_per_level(ocdid: str) -> dict[str, RoleConfig]:
    """Return (global, state, locality) RoleConfigs for a given ocdid."""
    state_ocdid = _state_ocdid_from_ocdid(ocdid)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        result: dict[str, RoleConfig] = {
            "global": RoleConfig(roles=await _fetch_roles_at_scope(cur, None)),
        }
        if state_ocdid:
            result["state"] = RoleConfig(
                roles=await _fetch_roles_at_scope(cur, state_ocdid)
            )
        if "/place:" in ocdid or "/county:" in ocdid:
            result["locality"] = RoleConfig(
                roles=await _fetch_roles_at_scope(cur, ocdid)
            )
    return result


async def get_global_config() -> RoleConfig:
    """Fetch all global roles."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        roles = await _fetch_roles_at_scope(cur, None)
    return RoleConfig(roles=roles)


# ── Pure decision helpers (functional core) ─────────────────────────────


def classify_term_op(
    entry: Role,
    existing: Role | None,
) -> tuple[TermOp, str | None]:
    """Pure: classify what should happen to a single role_entry row.
    Aliases are handled separately by diff_aliases.

    Compares all four tracked fields (label, status, is_unique, priority) —
    the bug that closed this function to only is_unique meant renaming a
    city's label returned NO_CHANGE and wrote nothing.

    Returns (op, change_log_type). change_log_type is None when op is NO_CHANGE
    (no role_entry write fires for this entry; alias-only changes still get
    logged separately as edit_role by the shell).
    """
    if existing is None:
        return (TermOp.ADD, "add_role")
    if (
        entry.label != existing.label
        or entry.status != existing.status
        or entry.is_unique != existing.is_unique
        or entry.priority != existing.priority
    ):
        return (TermOp.EDIT, "edit_role")
    return (TermOp.NO_CHANGE, None)


def diff_aliases(existing: list[str], incoming: list[str]) -> tuple[set[str], set[str]]:
    """Pure: (removed, added) given current and desired alias lists.

    Existing aliases come from the roles.aliases text[] column (a list
    in Python). Returns sets for the change_log payload.
    """
    return set(existing) - set(incoming), set(incoming) - set(existing)


def build_event_payload(
    entry: Role,
    aliases_added: set[str],
    aliases_removed: set[str],
) -> dict:
    """Pure: build the JSONB payload for a single role_entry's change_log event."""
    payload: dict = {"role": entry.label}
    if aliases_added:
        payload["aliases_added"] = sorted(aliases_added)
    if aliases_removed:
        payload["aliases_removed"] = sorted(aliases_removed)
    return payload


def reorder_validation_error(current: list[str], requested: list[str]) -> str | None:
    """Pure: a reorder must be a permutation of the scope's current canonical
    values. Returns an error message if it isn't (duplicate, missing, or
    unexpected role), else None. A stale client gets a clear 409 instead of
    silently dropping a role's priority."""
    if len(requested) != len(set(requested)):
        return "Reorder contains duplicate roles."
    missing = set(current) - set(requested)
    extra = set(requested) - set(current)
    if missing or extra:
        return f"Reorder set mismatch (missing: {sorted(missing)}, unexpected: {sorted(extra)})."
    return None


# ── Imperative shell ────────────────────────────────────────────────────


async def _emit_change_log(
    cur,
    log_type: str,
    jurisdiction_ocdid: str | None,
    payload: dict,
    user_id: str | None,
):
    await cur.execute(
        "INSERT INTO change_logs (type, jurisdiction_ocdid, changes, user_id) VALUES (%s, %s, %s, %s)",
        (log_type, jurisdiction_ocdid, json.dumps(payload), user_id),
    )


async def replace_roles_at_scope(
    jurisdiction_ocdid: str | None,
    entries: list[Role],
    user_id: str | None,
) -> None:
    """Replace all roles at a given scope. Emits one change_log per
    affected entry — alias deltas fold into the entry's event payload.

    Aliases are written wholesale as the text[] array on roles.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Read existing entries for this scope, keyed by label.
            await cur.execute(
                """
                SELECT label, id, status, is_unique, priority, aliases
                FROM roles
                WHERE scope IS NOT DISTINCT FROM %s
                """,
                (jurisdiction_ocdid,),
            )
            existing_by_label: dict[str, dict] = {}
            for row in await cur.fetchall():
                existing_by_label[row[0]] = {
                    "id": row[1],
                    "status": row[2],
                    "is_unique": row[3],
                    "priority": row[4],
                    "aliases": row[5],
                }

            # Removals: entries in existing but not in incoming.
            incoming_labels = {e.label for e in entries}
            for label in set(existing_by_label) - incoming_labels:
                await cur.execute(
                    "DELETE FROM roles WHERE id = %s",
                    (existing_by_label[label]["id"],),
                )
                await _emit_change_log(
                    cur,
                    "delete_role",
                    jurisdiction_ocdid,
                    {"role": label},
                    user_id,
                )

            # Adds and edits.
            for entry in entries:
                existing_entry = existing_by_label.get(entry.label)
                existing_role = (
                    Role(
                        label=entry.label,
                        status=existing_entry["status"],
                        is_unique=existing_entry["is_unique"],
                        priority=existing_entry["priority"],
                        aliases=existing_entry["aliases"],
                    )
                    if existing_entry
                    else None
                )

                op, log_type = classify_term_op(entry, existing_role)

                if op == TermOp.ADD:
                    await cur.execute(
                        """
                        INSERT INTO roles (label, scope, status, is_unique, priority, aliases)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            entry.label,
                            jurisdiction_ocdid,
                            entry.status,
                            entry.is_unique,
                            entry.priority,
                            entry.aliases,
                        ),
                    )
                elif op == TermOp.EDIT:
                    assert existing_entry is not None
                    await cur.execute(
                        """
                        UPDATE roles
                        SET label = %s, status = %s, is_unique = %s, priority = %s, aliases = %s
                        WHERE id = %s
                        """,
                        (
                            entry.label,
                            entry.status,
                            entry.is_unique,
                            entry.priority,
                            entry.aliases,
                            existing_entry["id"],
                        ),
                    )
                else:  # NO_CHANGE — aliases may still differ
                    assert existing_entry is not None
                    if existing_entry["aliases"] != entry.aliases:
                        await cur.execute(
                            "UPDATE roles SET aliases = %s WHERE id = %s",
                            (entry.aliases, existing_entry["id"]),
                        )

                # Compute alias diffs for the change_log regardless of op.
                existing_aliases = existing_entry["aliases"] if existing_entry else []
                added, removed = diff_aliases(existing_aliases, entry.aliases)
                payload = build_event_payload(entry, added, removed)

                if log_type is not None:
                    await _emit_change_log(
                        cur, log_type, jurisdiction_ocdid, payload, user_id
                    )
                elif added or removed:
                    await _emit_change_log(
                        cur, "edit_role", jurisdiction_ocdid, payload, user_id
                    )

        await conn.commit()


async def reorder_roles_at_scope(
    jurisdiction_ocdid: str | None,
    role_order: list[str],
    user_id: str | None,
    moved_roles: list[str] | None = None,
) -> None:
    """Set role_entry priority = position in role_order at a scope.
    role_order must be a permutation of the scope's current role labels.
    moved_roles names the labels the user actively moved (folded into the
    change_log so the summary can list them, not just the furthest shift).
    Emits one reorder_roles change_log; an unchanged order writes nothing."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT label
                FROM roles
                WHERE scope IS NOT DISTINCT FROM %s
                ORDER BY priority NULLS LAST, label
                """,
                (jurisdiction_ocdid,),
            )
            before = [row[0] for row in await cur.fetchall()]

            error = reorder_validation_error(before, role_order)
            if error:
                raise RuntimeError(error)

            if before == role_order:
                return  # nothing moved — don't write a phantom event

            for position, label in enumerate(role_order):
                await cur.execute(
                    """
                    UPDATE roles SET priority = %s
                    WHERE label = %s AND scope IS NOT DISTINCT FROM %s
                    """,
                    (position, label, jurisdiction_ocdid),
                )

            payload: dict = {"before": before, "after": role_order}
            requested = set(role_order)
            valid_moved = [role for role in (moved_roles or []) if role in requested]
            if valid_moved:
                payload["moved"] = valid_moved
            await _emit_change_log(
                cur, "reorder_roles", jurisdiction_ocdid, payload, user_id
            )
        await conn.commit()


async def delete_role(
    label: str, jurisdiction_ocdid: str | None, user_id: str | None
) -> None:
    """Hard-delete a role_entry. Does nothing if no matching entry exists."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM roles
                WHERE label = %s AND scope IS NOT DISTINCT FROM %s
                RETURNING id
                """,
                (label, jurisdiction_ocdid),
            )
            if await cur.fetchone() is None:
                return  # nothing to delete; don't log a phantom event
            await _emit_change_log(
                cur,
                "delete_role",
                jurisdiction_ocdid,
                {"role": label},
                user_id,
            )
        await conn.commit()