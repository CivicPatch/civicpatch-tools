"""Patching a jurisdiction entry. Pure — no I/O, no GitHub, no DB.

Mirrors people_edits.py: the service fetches the file and opens the PR; deciding
what the patch *is* and what it does to the document happens here, where it can be
tested with no mocks.
"""

import copy
from typing import TypedDict, cast


class JurisdictionPatch(TypedDict, total=False):
    """The editable half of a jurisdictions.yml entry; everything else is upstream-owned or
    derived.

    `total=False` is the contract, not laxness: any subset of these keys may be present, which
    is what JSON Merge Patch means. It also types the `before` side, whose keys are the patch's
    by construction — though those values come from YAML and are validated by nothing, so on
    that side the types describe intent rather than a guarantee.
    """

    url: str | None
    population: int | None
    geoid: str | None


# Derived, so adding a field to the request model cannot leave this behind.
PATCHABLE_FIELDS = tuple(JurisdictionPatch.__optional_keys__)


def build_patch(fields: dict) -> JurisdictionPatch:
    """Keep only the patchable keys the caller actually sent.

    JSON Merge Patch semantics, matching people_edits: a key that is absent is left alone,
    and a key sent as None was explicitly set to null by a human and is written as null.
    That distinction cannot be made after the fact, so `fields` must already carry only what
    was provided — see the router's model_dump(exclude_unset=True).
    """
    # cast: the comprehension filters to exactly the TypedDict's keys, which a checker cannot
    # see through a runtime membership test.
    return cast(
        JurisdictionPatch,
        {key: value for key, value in fields.items() if key in PATCHABLE_FIELDS},
    )


def find_jurisdiction(doc: dict, jurisdiction_ocdid: str) -> dict | None:
    for entry in doc.get("jurisdictions", []):
        if entry.get("id") == jurisdiction_ocdid:
            return entry
    return None


def current_values(entry: dict, patch: JurisdictionPatch) -> JurisdictionPatch:
    """What the patched keys hold now — the "before" side of the change."""
    return cast(JurisdictionPatch, {key: entry.get(key) for key in patch})


def apply_patch(doc: dict, jurisdiction_ocdid: str, patch: JurisdictionPatch) -> dict:
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
