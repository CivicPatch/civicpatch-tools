from enum import StrEnum
from typing import Any

from pydantic import BaseModel


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


class Assertion(BaseModel):
    entity_type: EntityType
    entity_id: str
    field_path: str
    kind: AssertionKind
    value: Any
    sources: list[Source] = []
    # Which changeset this claim was made under, if any — a direct field assert or an edit
    # outside review has none. Write-once in practice; nothing updates it after insert.
    changeset_id: str | None = None
