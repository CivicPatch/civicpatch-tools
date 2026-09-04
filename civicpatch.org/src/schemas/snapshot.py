"""One jurisdiction's tree at a moment, and the difference between two of them.

The shapes `core.snapshot_diff` compares. Deliberately not the `shared.schemas` models: those
are API projections — `Membership` carries no `id` and no `closed_at`, so two of them cannot be
matched across a write or told apart when a seat closes.
"""

from pydantic import BaseModel, JsonValue

from schemas.assertions import EntityType


class Entity(BaseModel):
    """One row, as a bag of comparable fields.

    `fields` is a mapping rather than a model per entity type, which is what makes `diff`
    polymorphic: it never learns what a post is. Adding organizations to the tree is a change to
    the query that builds a `Snapshot`, and none at all to the comparison.
    """

    entity_type: EntityType
    entity_id: str
    fields: dict[str, JsonValue]


class Snapshot(BaseModel):
    entities: list[Entity] = []


class Change(BaseModel):
    """One field of one row, moving.

    `before is None` covers both "was unset" and "the row did not exist"; `after is None` covers
    both "was cleared" and "the row is gone". The distinction is not worth a `kind`: a reader
    wants "Jane Smith, 5 fields", which is a grouping of these, and a sink wants only that
    something moved here at all.
    """

    entity_type: EntityType
    entity_id: str
    field_path: str
    before: JsonValue | None = None
    after: JsonValue | None = None
