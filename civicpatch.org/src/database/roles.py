"""Database queries for the role taxonomy (role_terms + role_aliases).

role_terms holds the curated role vocabulary; role_aliases attach to a term.
"""

import json
from enum import Enum

from database.database import get_pool
from schemas.jurisdictions import RoleEntryData
from shared.utils.config_utils import RoleConfig, RoleEntry


class TermOp(str, Enum):
    ADD = "add"  # insert a new role_term
    EDIT = "edit"  # UPDATE existing term's tracked fields (e.g. is_unique)
    # NO_CHANGE: term row stays as-is. Common case — the PUT sent the same
    # value with the same tracked fields. The shell still runs the alias sync
    # for this term because the incoming entry's `aliases:` list can differ
    # from what's currently in role_aliases.
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


async def _fetch_terms_at_scope(cur, jurisdiction_ocdid: str | None) -> list[RoleEntry]:
    """Fetch all role_terms at a single scope, with active aliases."""
    await cur.execute(
        """
        SELECT t.value, t.is_unique,
               COALESCE(
                   jsonb_agg(ra.value ORDER BY ra.created_at)
                       FILTER (WHERE ra.value IS NOT NULL),
                   '[]'::jsonb
               ) AS aliases
        FROM role_terms t
        LEFT JOIN role_aliases ra ON ra.term_id = t.id AND ra.disabled_at IS NULL
        WHERE t.jurisdiction_ocdid IS NOT DISTINCT FROM %s
        GROUP BY t.id, t.value, t.priority
        ORDER BY t.priority, t.value
        """,
        (jurisdiction_ocdid,),
    )
    return [
        RoleEntry(role=value, is_unique=is_unique, aliases=aliases)
        for value, is_unique, aliases in await cur.fetchall()
    ]


async def get_role_config_per_level(ocdid: str) -> dict[str, RoleConfig]:
    """Return (global, state, locality) RoleConfigs for a given ocdid."""
    state_ocdid = _state_ocdid_from_ocdid(ocdid)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        result: dict[str, RoleConfig] = {
            "global": RoleConfig(roles=await _fetch_terms_at_scope(cur, None)),
        }
        if state_ocdid:
            result["state"] = RoleConfig(
                roles=await _fetch_terms_at_scope(cur, state_ocdid)
            )
        if "/place:" in ocdid or "/county:" in ocdid:
            result["locality"] = RoleConfig(
                roles=await _fetch_terms_at_scope(cur, ocdid)
            )
    return result


async def get_global_config() -> RoleConfig:
    """Fetch all global role_terms."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        terms = await _fetch_terms_at_scope(cur, None)
    return RoleConfig(roles=terms)


# ── Pure decision helpers (functional core) ─────────────────────────────


def classify_term_op(
    entry: RoleEntryData,
    term_exists: bool,
    existing_is_unique: bool | None = None,
) -> tuple[TermOp, str | None]:
    """Pure: classify what should happen to a single term at the term-row level.
    Aliases are handled separately by diff_aliases.

    Returns (op, change_log_type). change_log_type is None when op is NO_CHANGE
    (no term-row write fires for this entry; alias-only changes still get
    logged separately as edit_role by the shell).
    """
    if not term_exists:
        return (TermOp.ADD, "add_role")
    if existing_is_unique is not None and entry.is_unique != existing_is_unique:
        return (TermOp.EDIT, "edit_role")
    return (TermOp.NO_CHANGE, None)


def diff_aliases(existing: set[str], incoming: list[str]) -> tuple[set[str], set[str]]:
    """Pure: (to_disable, to_add) given current and desired alias sets."""
    inc = set(incoming)
    return existing - inc, inc - existing


def build_event_payload(
    entry: RoleEntryData,
    aliases_added: set[str],
    aliases_removed: set[str],
) -> dict:
    """Pure: build the JSONB payload for a single term's change_log event."""
    payload: dict = {"role": entry.role}
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


async def _apply_alias_diff(
    cur, term_id: str, incoming_aliases: list[str]
) -> tuple[set[str], set[str]]:
    """Apply alias changes for a term; return (added, removed) sets for logging."""
    await cur.execute(
        "SELECT value FROM role_aliases WHERE disabled_at IS NULL AND term_id = %s",
        (term_id,),
    )
    existing = {r[0] for r in await cur.fetchall()}
    to_disable, to_add = diff_aliases(existing, incoming_aliases)

    for alias in to_disable:
        await cur.execute(
            "UPDATE role_aliases SET disabled_at = now() WHERE term_id = %s AND value = %s AND disabled_at IS NULL",
            (term_id, alias),
        )
    for alias in to_add:
        await cur.execute(
            "INSERT INTO role_aliases (term_id, value, source) VALUES (%s, %s, 'curated')",
            (term_id, alias),
        )
    return to_add, to_disable


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
    entries: list[RoleEntryData],
    user_id: str | None,
) -> None:
    """Replace all role_terms at a given scope. Emits one change_log per
    affected term — alias deltas fold into the term's event payload."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id::text, value, is_unique FROM role_terms WHERE jurisdiction_ocdid IS NOT DISTINCT FROM %s",
                (jurisdiction_ocdid,),
            )
            existing = {
                row[1]: {"id": row[0], "is_unique": row[2]}
                for row in await cur.fetchall()
            }

            # Removals: terms in existing but not in incoming.
            incoming_values = {e.role for e in entries}
            for value in set(existing) - incoming_values:
                await cur.execute(
                    "DELETE FROM role_terms WHERE id = %s", (existing[value]["id"],)
                )
                await _emit_change_log(
                    cur,
                    "delete_role",
                    jurisdiction_ocdid,
                    {"role": value},
                    user_id,
                )

            # Adds and edits.
            for entry in entries:
                existing_entry = existing.get(entry.role)
                op, log_type = classify_term_op(
                    entry,
                    existing_entry is not None,
                    existing_entry["is_unique"] if existing_entry else None,
                )

                if op == TermOp.ADD:
                    # New canonical roles land at the bottom (max priority + 1), not 0 —
                    # priority 0 is now a real position (the top), so defaulting there
                    # would dislodge whatever the taxonomy was ordered to lead with.
                    # `kind` is a leftover NOT NULL column — see DATABASE.md cleanup TBD.
                    await cur.execute(
                        """
                        INSERT INTO role_terms (value, kind, jurisdiction_ocdid, display_name, is_unique, priority)
                        VALUES (%s, 'canonical', %s, %s, %s,
                            COALESCE((SELECT MAX(priority) + 1 FROM role_terms
                                      WHERE jurisdiction_ocdid IS NOT DISTINCT FROM %s), 0))
                        RETURNING id::text
                        """,
                        (
                            entry.role,
                            jurisdiction_ocdid,
                            entry.role,
                            entry.is_unique,
                            jurisdiction_ocdid,
                        ),
                    )
                    row = await cur.fetchone()
                    assert row, "INSERT ... RETURNING id returned no row"
                    term_id = row[0]
                elif op == TermOp.EDIT:
                    assert existing_entry is not None
                    term_id = existing_entry["id"]
                    await cur.execute(
                        "UPDATE role_terms SET is_unique = %s WHERE id = %s",
                        (entry.is_unique, term_id),
                    )
                else:  # NO_CHANGE
                    assert existing_entry is not None
                    term_id = existing_entry["id"]

                added, removed = await _apply_alias_diff(cur, term_id, entry.aliases)
                payload = build_event_payload(entry, added, removed)

                # Emit one event per term: the term-level op if present, else edit_role
                # if aliases changed, else nothing.
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
    """Set canonical role priority = position in role_order at a scope.
    role_order must be a permutation of the scope's current canonical values.
    moved_roles names the values the user actively moved (folded into the
    change_log so the summary can list them, not just the furthest shift).
    Emits one reorder_roles change_log; an unchanged order writes nothing."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT value FROM role_terms
                WHERE jurisdiction_ocdid IS NOT DISTINCT FROM %s
                ORDER BY priority, value
                """,
                (jurisdiction_ocdid,),
            )
            before = [row[0] for row in await cur.fetchall()]

            error = reorder_validation_error(before, role_order)
            if error:
                raise RuntimeError(error)

            if before == role_order:
                return  # nothing moved — don't write a phantom event

            for position, value in enumerate(role_order):
                await cur.execute(
                    """
                    UPDATE role_terms SET priority = %s
                    WHERE value = %s AND jurisdiction_ocdid IS NOT DISTINCT FROM %s
                    """,
                    (position, value, jurisdiction_ocdid),
                )

            payload: dict = {"before": before, "after": role_order}
            # Only keep moved hints that are actually in this reorder — a stale
            # client can't poison the audit summary with unknown role values.
            requested = set(role_order)
            valid_moved = [role for role in (moved_roles or []) if role in requested]
            if valid_moved:
                payload["moved"] = valid_moved
            await _emit_change_log(
                cur, "reorder_roles", jurisdiction_ocdid, payload, user_id
            )
        await conn.commit()


async def delete_role(
    value: str, jurisdiction_ocdid: str | None, user_id: str | None
) -> None:
    """Hard-delete a role_term. Aliases cascade-delete via FK.
    RETURNING id tells us whether a row was actually removed, so an unmatched
    value doesn't log a phantom event."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM role_terms WHERE value = %s AND jurisdiction_ocdid IS NOT DISTINCT FROM %s RETURNING id",
                (value, jurisdiction_ocdid),
            )
            if await cur.fetchone() is None:
                return  # nothing to delete; don't log a phantom event
            await _emit_change_log(
                cur,
                "delete_role",
                jurisdiction_ocdid,
                {"role": value},
                user_id,
            )
        await conn.commit()
