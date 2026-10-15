"""Decisions about the role taxonomy shared by the config sync and the config edits. Pure — no
I/O, no DB. Role writes go through open-data's config file (`core.role_config_edits`); the sync
applies a merged file to `roles` (`core.jurisdiction_config_sync`).
"""

import re
from enum import Enum


class RoleOp(str, Enum):
    ADD = "add"  # insert a new roles row
    EDIT = "edit"  # UPDATE the stored row's tracked fields
    # NO_CHANGE: row stays as-is; its aliases may still change.
    NO_CHANGE = "no_change"


def slugify_label(label: str) -> str:
    # Must match migration 109's backfill expression exactly, or a role minted
    # here and one minted by the migration disagree.
    return re.sub(r"[^a-zA-Z0-9]+", "-", label).lower().strip("-")


def diff_aliases(stored: list[str], incoming: list[str]) -> tuple[set[str], set[str]]:
    """Pure: (added, removed) given the current and desired alias lists.

    Added first, matching _sync_aliases' return and build_event_payload's
    parameters. It used to be the other way round, and a caller destructuring it
    added-first silently inverted every change_log.
    """
    return set(incoming) - set(stored), set(stored) - set(incoming)


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
