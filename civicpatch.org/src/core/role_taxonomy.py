"""Decisions about the role taxonomy. Pure — no I/O, no DB.

`database/roles.py` owns the SQL and the transaction; everything here decides
*what* should happen to a row, or whether a submitted set is coherent at all, and
is testable with no mocks.

Submitted roles (`RoleInput`) are matched against stored ones (`Role`) by exact
label, so **a rename is not expressible through this path** — an entry whose
label is not already stored is a new role, not a renamed one. Renaming and
merging are #2476.
"""

import re
from enum import Enum

from schemas.roles import RoleInput
from shared.schemas import Role


class RoleOp(str, Enum):
    ADD = "add"  # insert a new roles row
    EDIT = "edit"  # UPDATE the stored row's tracked fields
    # NO_CHANGE: row stays as-is. Common case — the PUT sent the same values for
    # every tracked field. The shell still syncs role_aliases for this row,
    # because the incoming `aliases:` list can differ from what's stored.
    NO_CHANGE = "no_change"


def slugify_label(label: str) -> str:
    # Must match migration 109's backfill expression exactly, or a role minted
    # here and one minted by the migration disagree.
    return re.sub(r"[^a-zA-Z0-9]+", "-", label).lower().strip("-")


def classify_role_op(entry: RoleInput, stored: Role | None) -> RoleOp:
    """Pure: what should happen to this role's row. Aliases are separate — see
    diff_aliases — so an entry can be NO_CHANGE and still have alias work.

    `label` is not compared: lookup is by exact label, so a matched role has the
    same one by construction. `priority` is not compared either — reorder_roles
    owns it, and RoleInput has no such field.
    """
    if stored is None:
        return RoleOp.ADD
    if entry.status != stored.status or entry.is_unique != stored.is_unique:
        return RoleOp.EDIT
    return RoleOp.NO_CHANGE


def diff_aliases(stored: list[str], incoming: list[str]) -> tuple[set[str], set[str]]:
    """Pure: (added, removed) given the current and desired alias lists.

    Added first, matching _sync_aliases' return and build_event_payload's
    parameters. It used to be the other way round, and a caller destructuring it
    added-first silently inverted every change_log.
    """
    return set(incoming) - set(stored), set(stored) - set(incoming)


def _claimed_names(
    entries: list[RoleInput],
    stored_by_label: dict[str, Role],
) -> list[tuple[str, str, bool]]:
    """Pure: every (name, owning role label, is_label) the taxonomy holds after
    the write. A submitted entry replaces the stored role of the same label, so
    that role's stored aliases are not carried over. A role's own label comes
    before its aliases."""
    submitted = {entry.label for entry in entries}
    claims = []
    for label, role in stored_by_label.items():
        if label in submitted:
            continue
        claims.append((label, label, True))
        for alias in role.aliases:
            claims.append((alias, label, False))
    for entry in entries:
        claims.append((entry.label, entry.label, True))
        for alias in entry.aliases:
            claims.append((alias, entry.label, False))
    return claims


def name_conflict_error(
    entries: list[RoleInput],
    stored_by_label: dict[str, Role],
) -> str | None:
    """Pure: labels and aliases share one case-insensitive namespace, so every
    matchable string must resolve to exactly one role.

    The DB enforces this within `roles` and within `role_aliases`, but a unique
    index cannot span two tables. Nothing stopped one role claiming another's
    label as an alias, and `get_role_alias_map` lets the last role written win —
    so which role owned the name depended on priority order, and a reorder could
    silently flip it.
    """
    seen: dict[str, tuple[str, str, bool]] = {}
    for name, owner, is_label in _claimed_names(entries, stored_by_label):
        key = name.lower()
        previous = seen.get(key)
        seen[key] = (name, owner, is_label)
        if previous is None:
            continue
        previous_name, previous_owner, previous_is_label = previous
        if previous_owner != owner:
            return (
                f"'{name}' is claimed by both '{previous_owner}' and '{owner}'. "
                "A label or alias must name exactly one role."
            )
        # Same role restating its own label as an alias is redundant, not
        # ambiguous — it resolves to itself, and seeded rows do it. Two of its
        # *aliases* colliding is fatal: role_aliases is unique on lower(label),
        # so the second insert would fail.
        if not previous_is_label and not is_label:
            return f"'{owner}' lists '{previous_name}' more than once."
    return None


def slug_conflict_error(
    entries: list[RoleInput],
    stored_by_label: dict[str, Role],
) -> str | None:
    """Pure: slugging is lossy — 'Council/Member' and 'Council Member' both
    reduce to 'council-member', which `unique (lower(label))` lets through and
    the primary key then rejects.

    Only a new role mints a slug; an entry matching a stored label keeps the id
    that role already has.
    """
    owner_by_id = {role.id: label for label, role in stored_by_label.items()}
    for entry in entries:
        if entry.label in stored_by_label:
            continue
        role_id = slugify_label(entry.label)
        owner = owner_by_id.get(role_id)
        if owner is not None:
            return (
                f"'{entry.label}' and '{owner}' both reduce to the id "
                f"'{role_id}'. Rename one of them."
            )
        owner_by_id[role_id] = entry.label
    return None


def build_event_payload(
    label: str,
    aliases_added: set[str],
    aliases_removed: set[str],
) -> dict:
    """Pure: build the JSONB payload for a single role's change_log event."""
    payload: dict = {"role": label}
    if aliases_added:
        payload["aliases_added"] = sorted(aliases_added)
    if aliases_removed:
        payload["aliases_removed"] = sorted(aliases_removed)
    return payload


def change_log_type(op: RoleOp) -> str:
    """Pure: the event an op is recorded as. NO_CHANGE reaches here only when the
    row stood but its aliases moved, which is still an edit."""
    return "add_role" if op is RoleOp.ADD else "edit_role"


def reorder_validation_error(current: list[str], requested: list[str]) -> str | None:
    """Pure: a reorder must be a permutation of the current role ids.
    Returns an error message if it isn't (duplicate, missing, or unexpected
    role), else None. A stale client gets a clear 409 instead of silently
    dropping a role's priority."""
    if len(requested) != len(set(requested)):
        return "Reorder contains duplicate roles."
    missing = set(current) - set(requested)
    extra = set(requested) - set(current)
    if missing or extra:
        return f"Reorder set mismatch (missing: {sorted(missing)}, unexpected: {sorted(extra)})."
    return None
