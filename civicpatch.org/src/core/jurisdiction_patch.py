"""Patching a jurisdiction entry. Pure — no I/O, no GitHub, no DB.

Mirrors people_edits.py: the service fetches the file and opens the PR; deciding
what the patch *is* and what it does to the document happens here, where it can be
tested with no mocks.
"""

import copy

# Everything else in a jurisdictions.yml entry is upstream-owned or derived.
PATCHABLE_FIELDS = ("url", "population", "geoid")


def build_patch(fields: dict) -> dict:
    """Keep only the patchable keys the caller actually sent.

    JSON Merge Patch semantics, matching people_edits: a key that is absent is left alone,
    and a key sent as None was explicitly set to null by a human and is written as null.
    That distinction cannot be made after the fact, so `fields` must already carry only what
    was provided — see the router's model_dump(exclude_unset=True).
    """
    return {key: value for key, value in fields.items() if key in PATCHABLE_FIELDS}


def find_jurisdiction(doc: dict, jurisdiction_ocdid: str) -> dict | None:
    for entry in doc.get("jurisdictions", []):
        if entry.get("id") == jurisdiction_ocdid:
            return entry
    return None


def current_values(entry: dict, patch: dict) -> dict:
    """What the patched keys hold now — the "before" side of the change."""
    return {key: entry.get(key) for key in patch}


def apply_patch(doc: dict, jurisdiction_ocdid: str, patch: dict) -> dict:
    patched = copy.deepcopy(doc)
    for entry in patched.get("jurisdictions", []):
        if entry.get("id") == jurisdiction_ocdid:
            entry.update(patch)
    return patched


def patch_is_live(patch: dict, current: dict) -> bool:
    """True when every field the edit asked for already holds the requested value.

    An empty patch is never live: otherwise a malformed request would resolve itself.
    """
    if not patch:
        return False
    return all(current.get(key) == value for key, value in patch.items())
