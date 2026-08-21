from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EntityType(StrEnum):
    """What an assertion is about.

    Posts and memberships are single claims — "this office exists", "D held P from T1" — so an
    assertion about the whole entity is exact. A person is a bag of claims, which is why
    person assertions carry a `field_path` and whole-person ones do not exist: confirming "this
    person" would claim their email was checked when only their existence was.
    """

    POST = "post"
    MEMBERSHIP = "membership"
    PERSON = "person"


class AssertionKind(StrEnum):
    """What the human did.

    Not inferable from `value`: NULL there already means "deliberately empty" — a human
    asserting the clerk has no email — so a correction to nothing and a confirmation are
    indistinguishable without this.
    """

    # "You got it right, I checked." No value.
    CONFIRM = "confirm"
    # "You got it wrong, here is the right value."
    CORRECT = "correct"
    # "I asserted this earlier and I was wrong." The log is append-only, so a mistake is
    # retracted by a later row, never by deleting the first.
    RETRACT = "retract"


class Source(BaseModel):
    """Where an assertion came from. `note` may stand alone — "phoned the clerk" is the case
    that could not be a column, because the evidence exists nowhere else."""

    note: str | None = None
    url: str | None = None


class Assertion(BaseModel):
    """One thing a human said about one row, at one moment.

    `field_path` NULL means the entity itself rather than one of its fields.
    """

    entity_type: EntityType
    entity_id: str
    field_path: str | None = None
    kind: AssertionKind
    value: Any | None = None
    sources: list[Source] = []
