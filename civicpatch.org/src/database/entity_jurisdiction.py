"""What an asserted entity is — which jurisdiction it belongs to, and what to call it."""

from collections.abc import Mapping

from schemas.assertions import EntityType

# Keyed on `entity_type` rather than assuming person: the CHECK permits all three, so assuming
# would break silently on the first post assertion.
_SOURCES: dict[EntityType | str, str] = {
    EntityType.PERSON: "SELECT jurisdiction_ocdid FROM people WHERE id::text = %s",
    EntityType.POST: "SELECT jurisdiction_ocdid FROM posts WHERE id::text = %s",
    EntityType.MEMBERSHIP: (
        "SELECT p.jurisdiction_ocdid FROM memberships m "
        "JOIN posts p ON p.id = m.post_id WHERE m.id::text = %s"
    ),
}

# An assertion payload stores only ids, unlike person and post payloads which carry their own
# name. So a badge for one has to look its subject up — same keying, for the same reason.
#
# A post has no name of its own since migration 148 dropped `posts.label`; `roles.label` is what
# a reader recognises it by. A membership is named by whoever holds it.
_NAMES: dict[EntityType | str, str] = {
    EntityType.PERSON: "SELECT name FROM people WHERE id::text = %s",
    EntityType.POST: (
        "SELECT r.label FROM posts p JOIN roles r ON r.id = p.role_id WHERE p.id::text = %s"
    ),
    EntityType.MEMBERSHIP: (
        "SELECT pe.name FROM memberships m JOIN people pe ON pe.id = m.person_id "
        "WHERE m.id::text = %s"
    ),
}


async def _lookup(
    cur,
    queries: Mapping[EntityType | str, str],
    entity_type: EntityType | str,
    entity_id: str,
) -> str | None:
    query = queries.get(entity_type)
    if query is None:
        return None
    await cur.execute(query, (entity_id,))
    row = await cur.fetchone()
    return row[0] if row else None


async def jurisdiction_for(cur, entity_type: EntityType, entity_id: str) -> str | None:
    """None when the entity is gone — an assertion still records, it just names no jurisdiction."""
    return await _lookup(cur, _SOURCES, entity_type, entity_id)


async def name_for(cur, entity_type: EntityType | str, entity_id: str) -> str | None:
    """None when the entity is gone; the caller falls back to the type, never to a bare id.

    `str` is accepted because the caller is reading a stored payload, where `entity_type` is
    plain JSON. `EntityType` is a `StrEnum`, so it hashes as its value and keys the table either
    way — the signature says so rather than leaving it to be discovered.
    """
    return await _lookup(cur, _NAMES, entity_type, entity_id)
