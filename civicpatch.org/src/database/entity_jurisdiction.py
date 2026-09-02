"""Which jurisdiction an asserted entity belongs to."""

from schemas.assertions import EntityType

# Keyed on `entity_type` rather than assuming person: the CHECK permits all three, so assuming
# would break silently on the first post assertion.
_SOURCES = {
    EntityType.PERSON: "SELECT jurisdiction_ocdid FROM people WHERE id::text = %s",
    EntityType.POST: "SELECT jurisdiction_ocdid FROM posts WHERE id::text = %s",
    EntityType.MEMBERSHIP: (
        "SELECT p.jurisdiction_ocdid FROM memberships m "
        "JOIN posts p ON p.id = m.post_id WHERE m.id::text = %s"
    ),
}


async def jurisdiction_for(cur, entity_type: EntityType, entity_id: str) -> str | None:
    """None when the entity is gone — an assertion still records, it just names no jurisdiction."""
    query = _SOURCES.get(entity_type)
    if query is None:
        return None
    await cur.execute(query, (entity_id,))
    row = await cur.fetchone()
    return row[0] if row else None
