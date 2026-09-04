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
    JURISDICTION = "jurisdiction"
    ORGANIZATION = "organization"


class AssertionKind(StrEnum):
    """What the human did. Verbs, to match.

    Neither is a button. `accept` is written at publish for each non-null value the reviewer
    saw, `reject` when they remove one — which is what retired `confirm`, a valueless kind that
    existed so somebody could say "I looked".
    """

    # "This value stands." One per scalar field; one per element on a list field.
    ACCEPT = "accept"
    # "Never this value." Suppresses that value only, so the scraper keeps looking and a
    # genuinely new answer still reaches review.
    REJECT = "reject"


class Source(BaseModel):
    """Where an assertion came from. `note` may stand alone — "phoned the clerk" is the case
    that could not be a column, because the evidence exists nowhere else."""

    note: str | None = None
    url: str | None = None


class Assertion(BaseModel):
    """One thing a human said about one row, at one moment.

    Always about one field, and always carrying a value: a claim about the row itself has no
    field to name, and vouching for a post is now recorded on the post.
    """

    entity_type: EntityType
    entity_id: str
    field_path: str
    kind: AssertionKind
    value: Any
    sources: list[Source] = []
