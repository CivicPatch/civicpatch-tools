"""Database queries for the role taxonomy (roles).

One flat list — migration 109 dropped `roles.scope`, so there is no inheritance
to resolve. `id` is a slug ("council-member"), derived from `label` on insert
and immutable after. Removal sets `status='inactive'`; nothing is hard-deleted.

The decisions live in `core.role_taxonomy`; this module owns the SQL and the
transaction around it.
"""

import json

from core.role_taxonomy import (
    RoleOp,
    build_event_payload,
    change_log_type,
    classify_role_op,
    diff_aliases,
    name_conflict_error,
    reorder_validation_error,
    slug_conflict_error,
    slugify_label,
)
from database.database import get_pool
from schemas.roles import RoleInput
from shared.schemas import Role, RoleAliasStatus, RoleStatus


async def _fetch_roles(cur) -> list[Role]:
    """Every role with only its *approved* aliases — a candidate alias must not
    reach the matcher. Takes a cursor so upsert_roles can read inside its own
    transaction rather than through a second connection."""
    await cur.execute(
        """
        SELECT r.id, r.label, r.status, r.is_unique, r.priority,
               COALESCE(
                   array_agg(a.label ORDER BY a.label) FILTER (WHERE a.id IS NOT NULL),
                   '{}'
               )
        FROM roles r
        LEFT JOIN role_aliases a ON a.role_id = r.id AND a.status = %s
        GROUP BY r.id, r.label, r.status, r.is_unique, r.priority
        ORDER BY r.priority NULLS LAST, r.label
        """,
        (RoleAliasStatus.ACTIVE,),
    )
    return [
        Role(
            id=id,
            label=label,
            status=status,
            is_unique=is_unique,
            priority=priority,
            aliases=aliases,
        )
        for id, label, status, is_unique, priority, aliases in await cur.fetchall()
    ]


async def get_role(cur, role_id: str) -> Role | None:
    """One role by id, or None. Aliases come back empty — callers wanting those want the
    whole taxonomy, not a single row."""
    await cur.execute(
        "SELECT id, label, status, is_unique, priority FROM roles WHERE id = %s",
        (role_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    id, label, status, is_unique, priority = row
    return Role(
        id=id, label=label, status=status, is_unique=is_unique, priority=priority
    )


async def get_roles() -> list[Role]:
    """Every role, ordered.

    Inactive and excluded roles are included: filtering those is the caller's
    decision, since the admin UI needs to see them and the pipeline does not.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await _fetch_roles(cur)


async def _emit_change_log(
    cur,
    log_type: str,
    payload: dict,
    user_id: str | None,
):
    await cur.execute(
        "INSERT INTO change_logs (type, jurisdiction_ocdid, changes, user_id) VALUES (%s, NULL, %s, %s)",
        (log_type, json.dumps(payload), user_id),
    )


async def _sync_aliases(
    cur,
    role_id: str,
    existing: list[str],
    incoming: list[str],
) -> tuple[set[str], set[str]]:
    """Bring one role's aliases in line with the submitted list, returning
    (added, removed) for the change_log.

    Submitted aliases land approved: a maintainer typing one *is* the approval.
    `candidate` is for a future auto-mint path, which is the case approval was
    designed for.
    """
    added, removed = diff_aliases(existing, incoming)
    for alias in sorted(removed):
        await cur.execute(
            "DELETE FROM role_aliases WHERE role_id = %s AND lower(label) = lower(%s)",
            (role_id, alias),
        )
    for alias in sorted(added):
        await cur.execute(
            "INSERT INTO role_aliases (role_id, label, status) VALUES (%s, %s, %s)",
            (role_id, alias, RoleAliasStatus.ACTIVE),
        )
    return added, removed


async def upsert_roles(entries: list[RoleInput], user_id: str | None) -> None:
    """Add or update the submitted roles, one change_log per affected row.

    Absence is NOT removal — a label missing from `entries` is left alone.
    Removal is deactivate_role.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            stored_by_label = {role.label: role for role in await _fetch_roles(cur)}

            # Pre-flight, before any write: these are the conflicts the DB would
            # raise as a bare UniqueViolation (a 500), plus the label-vs-alias
            # one it cannot see at all. Checked here so the message can name
            # both sides. The indexes stay as the concurrency backstop.
            name_error = name_conflict_error(entries, stored_by_label)
            if name_error:
                raise RuntimeError(name_error)
            slug_error = slug_conflict_error(entries, stored_by_label)
            if slug_error:
                raise RuntimeError(slug_error)

            for entry in entries:
                stored = stored_by_label.get(entry.label)
                op = classify_role_op(entry, stored)

                if stored is None:
                    role_id = slugify_label(entry.label)
                    # priority is left NULL, which `ORDER BY priority NULLS LAST`
                    # reads as unranked — a new role sorts last until someone
                    # reorders.
                    await cur.execute(
                        """
                        INSERT INTO roles (id, label, status, is_unique)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (role_id, entry.label, entry.status, entry.is_unique),
                    )
                else:
                    role_id = stored.id
                    if op is RoleOp.EDIT:
                        # `label` is absent because lookup matched on it, so it
                        # is already correct; `priority` because reorder_roles
                        # owns it; `id` because it must survive everything.
                        await cur.execute(
                            "UPDATE roles SET status = %s, is_unique = %s WHERE id = %s",
                            (entry.status, entry.is_unique, role_id),
                        )

                added, removed = await _sync_aliases(
                    cur, role_id, stored.aliases if stored else [], entry.aliases
                )

                if op is not RoleOp.NO_CHANGE or added or removed:
                    await _emit_change_log(
                        cur,
                        change_log_type(op),
                        build_event_payload(entry.label, added, removed),
                        user_id,
                    )

        await conn.commit()


async def reorder_roles(
    role_order: list[str],
    user_id: str | None,
    moved_roles: list[str] | None = None,
) -> None:
    """Set priority = position in role_order. role_order must be a permutation
    of the current role *ids*. moved_roles names the ids the user actively moved
    (folded into the change_log so the summary can list them, not just the
    furthest shift). Emits one reorder_roles change_log; an unchanged order
    writes nothing."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, label FROM roles ORDER BY priority NULLS LAST, label"
            )
            rows = await cur.fetchall()
            before = [row[0] for row in rows]
            label_by_id = {row[0]: row[1] for row in rows}

            error = reorder_validation_error(before, role_order)
            if error:
                raise RuntimeError(error)

            if before == role_order:
                return  # nothing moved — don't write a phantom event

            for position, role_id in enumerate(role_order):
                await cur.execute(
                    "UPDATE roles SET priority = %s WHERE id = %s",
                    (position, role_id),
                )

            # The payload is stored in labels, not ids: core.change_logs
            # renders it straight into the activity feed, where "moved Council
            # Member" reads and "moved council-member" does not.
            payload: dict = {
                "before": [label_by_id[role_id] for role_id in before],
                "after": [label_by_id[role_id] for role_id in role_order],
            }
            requested = set(role_order)
            valid_moved = [
                label_by_id[role_id]
                for role_id in (moved_roles or [])
                if role_id in requested
            ]
            if valid_moved:
                payload["moved"] = valid_moved
            await _emit_change_log(cur, "reorder_roles", payload, user_id)
        await conn.commit()


async def deactivate_role(role_id: str, user_id: str | None) -> bool:
    """Deactivate a role by id. Returns False if it does not exist or was
    already inactive — either way there is nothing to log.

    Logged as `delete_role`: the user's action is unchanged, only the storage
    consequence is, and adding a change_log type needs its own migration.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE roles SET status = %s
                WHERE id = %s AND status <> %s
                RETURNING label
                """,
                (RoleStatus.INACTIVE, role_id, RoleStatus.INACTIVE),
            )
            row = await cur.fetchone()
            if row is None:
                return False
            await _emit_change_log(cur, "delete_role", {"role": row[0]}, user_id)
        await conn.commit()
        return True
