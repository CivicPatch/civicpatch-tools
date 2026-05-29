"""Database queries for the role taxonomy (role_terms + role_aliases).

role_terms holds both canonical roles and exclusion patterns, distinguished
by kind. Aliases attach to a term regardless of kind, so exclude/include is
a kind UPDATE — aliases stay with the term automatically.
"""

import json
from enum import Enum

from database.database import get_pool
from schemas.jurisdictions import RoleEntryData
from shared.utils.config_utils import RoleConfig, RoleEntry


class TermKind(str, Enum):
    CANONICAL = "canonical"
    EXCLUSION = "exclusion"


class TermOp(str, Enum):
    ADD = "add"                # insert a new role_term
    FLIP_KIND = "flip_kind"    # UPDATE existing term's kind (canonical ↔ exclusion)
    EDIT = "edit"              # UPDATE existing term's tracked fields (e.g. is_unique)
                               # without changing kind
    # NO_CHANGE: term row stays as-is. Common case — the PUT sent the same
    # value with the same kind and same tracked fields. The shell still runs
    # the alias sync for this term because the incoming entry's `aliases:`
    # list can differ from what's currently in role_aliases.
    NO_CHANGE = "no_change"


def _kind_for(entry: RoleEntryData) -> TermKind:
    return TermKind(entry.kind)


def _state_ocdid_from_ocdid(ocdid: str) -> str | None:
    """Extract the state-level ocdid prefix from a full ocdid."""
    parts = ocdid.split("/")
    for i, p in enumerate(parts):
        if p.startswith("state:"):
            return "/".join(parts[: i + 1])
    return None


async def _fetch_terms_at_scope(cur, jurisdiction_ocdid: str | None) -> list[RoleEntry]:
    """Fetch all role_terms (canonical + exclusion) at a single scope, with active aliases."""
    await cur.execute(
        """
        SELECT t.value, t.kind, t.is_unique,
               COALESCE(
                   jsonb_agg(ra.value ORDER BY ra.created_at)
                       FILTER (WHERE ra.value IS NOT NULL),
                   '[]'::jsonb
               ) AS aliases
        FROM role_terms t
        LEFT JOIN role_aliases ra ON ra.term_id = t.id AND ra.disabled_at IS NULL
        WHERE t.jurisdiction_ocdid IS NOT DISTINCT FROM %s
        GROUP BY t.id, t.value, t.kind, t.priority
        ORDER BY t.priority, t.value
        """,
        (jurisdiction_ocdid,),
    )
    return [
        RoleEntry(
            role=value,
            is_unique=is_unique,
            aliases=aliases,
            kind=kind,
        )
        for value, kind, is_unique, aliases in await cur.fetchall()
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
            result["state"] = RoleConfig(roles=await _fetch_terms_at_scope(cur, state_ocdid))
        if "/place:" in ocdid or "/county:" in ocdid:
            result["locality"] = RoleConfig(roles=await _fetch_terms_at_scope(cur, ocdid))
    return result


async def get_global_config() -> RoleConfig:
    """Fetch all global role_terms (canonical + exclusion)."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        terms = await _fetch_terms_at_scope(cur, None)
    return RoleConfig(roles=terms)


# ── Pure decision helpers (functional core) ─────────────────────────────


def classify_term_op(
    entry: RoleEntryData,
    existing_kind: TermKind | None,
    existing_is_unique: bool | None = None,
) -> tuple[TermOp, str | None]:
    """Pure: classify what should happen to a single term at the term-row level.
    Aliases are handled separately by diff_aliases.

    Returns (op, change_log_type). change_log_type is None when op is NO_CHANGE
    (no term-row write fires for this entry; alias-only changes still get
    logged separately as edit_role by the shell).
    """
    incoming_kind = _kind_for(entry)
    if existing_kind is None:
        return (TermOp.ADD, "add_role")
    if existing_kind != incoming_kind:
        log = "exclude_role" if incoming_kind == TermKind.EXCLUSION else "include_role"
        return (TermOp.FLIP_KIND, log)
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
    """Pure: build the JSONB payload for a single term's change_log event.
    Includes kind so the type vocabulary doesn't have to encode it."""
    payload: dict = {"role": entry.role, "kind": _kind_for(entry).value}
    if aliases_added:
        payload["aliases_added"] = sorted(aliases_added)
    if aliases_removed:
        payload["aliases_removed"] = sorted(aliases_removed)
    return payload


# ── Imperative shell ────────────────────────────────────────────────────


async def _apply_alias_diff(cur, term_id: str, incoming_aliases: list[str]) -> tuple[set[str], set[str]]:
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


async def _emit_change_log(cur, log_type: str, jurisdiction_ocdid: str | None, payload: dict, user_id: str | None):
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
                "SELECT id::text, value, kind, is_unique FROM role_terms WHERE jurisdiction_ocdid IS NOT DISTINCT FROM %s",
                (jurisdiction_ocdid,),
            )
            existing = {
                row[1]: {"id": row[0], "kind": TermKind(row[2]), "is_unique": row[3]}
                for row in await cur.fetchall()
            }

            # Removals: terms in existing but not in incoming.
            incoming_values = {e.role for e in entries}
            for value in set(existing) - incoming_values:
                kind = existing[value]["kind"]
                await cur.execute("DELETE FROM role_terms WHERE id = %s", (existing[value]["id"],))
                await _emit_change_log(
                    cur, "delete_role", jurisdiction_ocdid,
                    {"role": value, "kind": kind.value}, user_id,
                )

            # Adds, kind flips, edits.
            for entry in entries:
                existing_entry = existing.get(entry.role)
                op, log_type = classify_term_op(
                    entry,
                    existing_entry["kind"] if existing_entry else None,
                    existing_entry["is_unique"] if existing_entry else None,
                )

                if op == TermOp.ADD:
                    await cur.execute(
                        """
                        INSERT INTO role_terms (value, kind, jurisdiction_ocdid, display_name, is_unique, priority)
                        VALUES (%s, %s, %s, %s, %s, 0) RETURNING id::text
                        """,
                        (entry.role, _kind_for(entry).value, jurisdiction_ocdid, entry.role, entry.is_unique),
                    )
                    row = await cur.fetchone()
                    assert row, "INSERT ... RETURNING id returned no row"
                    term_id = row[0]
                elif op == TermOp.FLIP_KIND:
                    assert existing_entry is not None
                    term_id = existing_entry["id"]
                    await cur.execute(
                        "UPDATE role_terms SET kind = %s WHERE id = %s",
                        (_kind_for(entry).value, term_id),
                    )
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
                    await _emit_change_log(cur, log_type, jurisdiction_ocdid, payload, user_id)
                elif added or removed:
                    await _emit_change_log(cur, "edit_role", jurisdiction_ocdid, payload, user_id)

        await conn.commit()


async def _flip_term_kind(value: str, jurisdiction_ocdid: str | None, new_kind: TermKind, log_type: str, user_id: str | None) -> None:
    """Shared impl for exclude_role / include_role — UPDATE kind, aliases stay attached."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE role_terms SET kind = %s WHERE value = %s AND jurisdiction_ocdid IS NOT DISTINCT FROM %s",
                (new_kind.value, value, jurisdiction_ocdid),
            )
            await _emit_change_log(
                cur, log_type, jurisdiction_ocdid,
                {"role": value, "kind": new_kind.value}, user_id,
            )
        await conn.commit()


async def exclude_role(value: str, jurisdiction_ocdid: str | None, user_id: str | None) -> None:
    """Flip a canonical role to an exclusion. Aliases stay attached to the term."""
    await _flip_term_kind(value, jurisdiction_ocdid, TermKind.EXCLUSION, "exclude_role", user_id)


async def include_role(value: str, jurisdiction_ocdid: str | None, user_id: str | None) -> None:
    """Flip an exclusion back to a canonical role. Aliases stay attached."""
    await _flip_term_kind(value, jurisdiction_ocdid, TermKind.CANONICAL, "include_role", user_id)


async def delete_role(value: str, jurisdiction_ocdid: str | None, user_id: str | None) -> None:
    """Hard-delete a role_term. Aliases cascade-delete via FK.
    DELETE ... RETURNING grabs the kind in one round-trip so the change_log
    payload can record what kind of term was removed."""
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM role_terms WHERE value = %s AND jurisdiction_ocdid IS NOT DISTINCT FROM %s RETURNING kind",
                (value, jurisdiction_ocdid),
            )
            row = await cur.fetchone()
            if row is None:
                return  # nothing to delete; don't log a phantom event
            kind = row[0]
            await _emit_change_log(
                cur, "delete_role", jurisdiction_ocdid,
                {"role": value, "kind": kind}, user_id,
            )
        await conn.commit()
