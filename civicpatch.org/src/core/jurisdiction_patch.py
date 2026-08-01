"""Patching a jurisdiction entry. Pure — no I/O, no GitHub, no DB.

Mirrors people_patch.py: the service fetches the file and opens the PR; deciding
what the patch *is* and what it does to the document happens here, where it can be
tested with no mocks.
"""

# Everything else in a jurisdictions.yml entry is upstream-owned or derived.
PATCHABLE_FIELDS = ("url", "population", "geoid")


def build_patch(fields: dict) -> dict:
    """Drop absent fields. None means "leave this alone", never "clear it" — the
    difference between a patch and an overwrite."""
    return {
        key: value
        for key, value in fields.items()
        if value is not None and key in PATCHABLE_FIELDS
    }


def find_jurisdiction(doc: dict, jurisdiction_ocdid: str) -> dict | None:
    for entry in doc.get("jurisdictions", []):
        if entry.get("id") == jurisdiction_ocdid:
            return entry
    return None


def current_values(entry: dict, patch: dict) -> dict:
    """What the patched keys hold now — the "before" side of the change."""
    return {key: entry.get(key) for key in patch}


def apply_patch(doc: dict, jurisdiction_ocdid: str, patch: dict) -> dict:
    """A copy of doc with the patch applied. The original is left untouched, so a
    caller can still read the pre-edit values off it."""
    entries = doc.get("jurisdictions", [])
    patched = [
        {**entry, **patch} if entry.get("id") == jurisdiction_ocdid else entry
        for entry in entries
    ]
    return {**doc, "jurisdictions": patched}


def patch_is_live(patch: dict, current: dict) -> bool:
    """True when every field the edit asked for already holds the requested value.

    An empty patch is never live: otherwise a malformed request would resolve itself.
    """
    if not patch:
        return False
    return all(current.get(key) == value for key, value in patch.items())
