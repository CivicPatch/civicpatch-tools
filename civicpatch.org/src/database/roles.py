"""Database queries for the role taxonomy tables (roles, role_aliases, role_exclusions)."""

import json

from database.database import get_pool
from schemas.jurisdictions import RoleEntryData
from shared.utils.config_utils import RoleConfig, RoleEntry


def _state_ocdid_from_ocdid(ocdid: str) -> str | None:
    """Extract the state-level ocdid prefix from a full ocdid.

    'ocd-jurisdiction/country:us/state:tx/place:combes' → 'ocd-jurisdiction/country:us/state:tx'
    """
    parts = ocdid.split("/")
    for i, p in enumerate(parts):
        if p.startswith("state:"):
            return "/".join(parts[: i + 1])
    return None


async def _fetch_role_entries(cur, jurisdiction_ocdid: str | None) -> list[RoleEntry]:
    """Fetch roles + their aliases at a single scope level."""
    await cur.execute(
        """
        SELECT r.value, r.is_unique,
               COALESCE(
                   jsonb_agg(ra.value ORDER BY ra.created_at)
                       FILTER (WHERE ra.value IS NOT NULL),
                   '[]'::jsonb
               ) AS aliases
        FROM roles r
        LEFT JOIN role_aliases ra ON ra.role_id = r.id AND ra.disabled_at IS NULL
        WHERE r.disabled_at IS NULL
          AND r.jurisdiction_ocdid IS NOT DISTINCT FROM %s
        GROUP BY r.id, r.value, r.is_unique, r.priority
        ORDER BY r.priority, r.value
        """,
        (jurisdiction_ocdid,),
    )
    return [RoleEntry(role=r[0], is_unique=r[1], aliases=r[2]) for r in await cur.fetchall()]


async def _fetch_exclusion_entries(cur, jurisdiction_ocdid: str | None) -> list[RoleEntry]:
    """Fetch exclusion patterns at a single scope level as include: false entries."""
    await cur.execute(
        "SELECT value FROM role_exclusions WHERE disabled_at IS NULL AND jurisdiction_ocdid IS NOT DISTINCT FROM %s ORDER BY value",
        (jurisdiction_ocdid,),
    )
    return [RoleEntry(role=r[0], is_unique=False, include=False) for r in await cur.fetchall()]


async def get_role_config_per_level(ocdid: str) -> dict[str, RoleConfig]:
    """Return (global, state, locality) RoleConfigs for a given ocdid.

    Each level includes both roles and exclusions (as include: false entries)
    so the output is backward-compatible with the old GitHub-sourced shape.
    """
    state_ocdid = _state_ocdid_from_ocdid(ocdid)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        global_roles = await _fetch_role_entries(cur, None)
        global_excls = await _fetch_exclusion_entries(cur, None)
        result: dict[str, RoleConfig] = {
            "global": RoleConfig(roles=global_roles + global_excls),
        }

        if state_ocdid:
            state_roles = await _fetch_role_entries(cur, state_ocdid)
            state_excls = await _fetch_exclusion_entries(cur, state_ocdid)
            result["state"] = RoleConfig(roles=state_roles + state_excls)

        if "/place:" in ocdid or "/county:" in ocdid:
            local_roles = await _fetch_role_entries(cur, ocdid)
            local_excls = await _fetch_exclusion_entries(cur, ocdid)
            result["locality"] = RoleConfig(roles=local_roles + local_excls)

    return result


async def get_global_config() -> RoleConfig:
    """Fetch all active global roles + exclusions."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        roles = await _fetch_role_entries(cur, None)
        excls = await _fetch_exclusion_entries(cur, None)
    return RoleConfig(roles=roles + excls)


async def replace_roles_at_scope(
    jurisdiction_ocdid: str | None,
    entries: list[RoleEntryData],
    user_id: str | None,
) -> None:
    """Replace all active role entries (roles + exclusions) at a given scope level.

    Diffes existing vs incoming entries, soft-disables removed items, upserts
    new ones, syncs aliases per-role, and writes change_log entries.
    """
    role_entries = [e for e in entries if e.include]
    excl_entries = [e for e in entries if not e.include]

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            changes = []

            # ── Sync roles ──────────────────────────────────────────
            await cur.execute(
                "SELECT id::text, value, is_unique FROM roles WHERE disabled_at IS NULL AND jurisdiction_ocdid IS NOT DISTINCT FROM %s",
                (jurisdiction_ocdid,),
            )
            existing = {r[1]: {"id": r[0], "is_unique": r[2]} for r in await cur.fetchall()}

            incoming_names = {e.role for e in role_entries}
            to_disable = set(existing) - incoming_names
            to_add = incoming_names - set(existing)

            for name in to_disable:
                await cur.execute("UPDATE roles SET disabled_at = now() WHERE id = %s", (existing[name]["id"],))
                changes.append({"action": "disable_role", "role": name})

            for entry in role_entries:
                if entry.role in to_add:
                    await cur.execute(
                        "INSERT INTO roles (value, display_name, jurisdiction_ocdid, is_unique, priority) VALUES (%s, %s, %s, %s, 0) RETURNING id::text",
                        (entry.role, entry.role, jurisdiction_ocdid, entry.is_unique),
                    )
                    row = await cur.fetchone()
                    assert row, "INSERT ... RETURNING id returned no row"
                    role_id = row[0]
                    changes.append({"action": "add_role", "role": entry.role, "role_id": role_id})
                else:
                    role_id = existing[entry.role]["id"]

                # Sync aliases for this role
                await cur.execute(
                    "SELECT value FROM role_aliases WHERE disabled_at IS NULL AND role_id = %s",
                    (role_id,),
                )
                existing_aliases = {r[0] for r in await cur.fetchall()}
                incoming_aliases = set(entry.aliases)

                for alias in existing_aliases - incoming_aliases:
                    await cur.execute(
                        "UPDATE role_aliases SET disabled_at = now() WHERE role_id = %s AND value = %s AND disabled_at IS NULL",
                        (role_id, alias),
                    )
                    changes.append({"action": "disable_role_alias", "role": entry.role, "alias": alias})

                for alias in incoming_aliases - existing_aliases:
                    await cur.execute(
                        "INSERT INTO role_aliases (role_id, value, source) VALUES (%s, %s, 'curated') ON CONFLICT (role_id, value) WHERE disabled_at IS NULL DO NOTHING",
                        (role_id, alias),
                    )
                    changes.append({"action": "add_role_alias", "role": entry.role, "alias": alias})

            # ── Sync exclusions ─────────────────────────────────────
            await cur.execute(
                "SELECT id::text, value FROM role_exclusions WHERE disabled_at IS NULL AND jurisdiction_ocdid IS NOT DISTINCT FROM %s",
                (jurisdiction_ocdid,),
            )
            existing_excl = {r[1]: r[0] for r in await cur.fetchall()}

            incoming_excl_names = {e.role for e in excl_entries}
            for name in existing_excl:
                if name not in incoming_excl_names:
                    await cur.execute("UPDATE role_exclusions SET disabled_at = now() WHERE id = %s", (existing_excl[name],))
                    changes.append({"action": "disable_role_exclusion", "value": name})

            for entry in excl_entries:
                if entry.role not in existing_excl:
                    await cur.execute(
                        "INSERT INTO role_exclusions (value, jurisdiction_ocdid, source) VALUES (%s, %s, 'curated') ON CONFLICT (value, jurisdiction_ocdid) WHERE disabled_at IS NULL DO NOTHING",
                        (entry.role, jurisdiction_ocdid),
                    )
                    # Also add exclusion aliases
                    for alias in entry.aliases:
                        await cur.execute(
                            "INSERT INTO role_exclusions (value, jurisdiction_ocdid, source) VALUES (%s, %s, 'curated') ON CONFLICT (value, jurisdiction_ocdid) WHERE disabled_at IS NULL DO NOTHING",
                            (alias, jurisdiction_ocdid),
                        )
                    changes.append({"action": "add_role_exclusion", "value": entry.role})

            # ── Write change_logs ──────────────────────────────────
            for change in changes:
                await cur.execute(
                    "INSERT INTO change_logs (type, jurisdiction_ocdid, changes, user_id) VALUES (%s, %s, %s, %s)",
                    (change["action"], jurisdiction_ocdid, json.dumps(change), user_id),
                )

        await conn.commit()