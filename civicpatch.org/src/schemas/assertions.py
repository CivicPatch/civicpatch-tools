from enum import StrEnum
from typing import Any

from pydantic import BaseModel, field_validator, model_validator


class EntityType(StrEnum):
    POST = "post"
    MEMBERSHIP = "membership"
    PERSON = "person"
    JURISDICTION = "jurisdiction"
    ORGANIZATION = "organization"
    # What a withdraw names: a fact, by its row id.
    SOURCE_RECORD = "source_record"
    SOURCE_PAGE = "source_page"
    CLAIM = "claim"


class AssertionKind(StrEnum):
    # "This value stands." One per scalar field; one per element on a list field.
    ACCEPT = "accept"
    # "Never this value." Suppresses that value only, so the scraper keeps looking and a
    # genuinely new answer still reaches review.
    REJECT = "reject"
    # "This fact no longer counts." Names a whole row (entity_type claim, source_record or
    # source_page), carries no field and no value, and can itself be withdrawn: that is undo.
    WITHDRAW = "withdraw"


class Source(BaseModel):
    note: str | None = None
    url: str | None = None

    @model_validator(mode="after")
    def _note_or_url(self) -> "Source":
        if not (self.note or self.url):
            raise ValueError("a source needs a note or a url")
        return self


class DefaultNote(StrEnum):
    """What a claim says about itself when the caller supplied no source of its own.

    `Source.note` stays free text: a human's typed reason is a note too, and must not be
    narrowed to this set.
    """

    EDITED = "edited"
    ASSIGNED = "assigned"
    LABEL_SET = "label set"
    # Honest, where inventing an act name would not be, and the routes that carry a real
    # reason still carry it.
    NO_REASON = "no reason given"
    WITHDRAWN = "withdrawn"


class Assertion(BaseModel):
    entity_type: EntityType
    entity_id: str
    field_path: str
    kind: AssertionKind
    value: Any
    # Where the claim came from — a url or a note. Required: a claim nobody can trace is the
    # thing this field exists to prevent (§5).
    sources: list[Source]
    # Which changeset this claim was made under, if any — a direct field assert or an edit
    # outside review has none. Write-once in practice; nothing updates it after insert.
    changeset_id: str | None = None

    @field_validator("sources")
    @classmethod
    def _has_a_source(cls, sources: list[Source]) -> list[Source]:
        if not sources:
            raise ValueError("a claim needs a source")
        return sources
