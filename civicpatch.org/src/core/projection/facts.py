from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EntityType(StrEnum):
    PERSON = "person"
    POST = "post"
    MEMBERSHIP = "membership"
    JURISDICTION = "jurisdiction"
    ORGANIZATION = "organization"
    # Facts can be claimed about too: a withdraw names one, and a split is a `person_id` claim
    # on a record. Not yet in the `assertions_entity_type_check` constraint.
    SOURCE_RECORD = "source_record"
    SOURCE_PAGE = "source_page"
    CLAIM = "claim"


class ClaimKind(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    # Not yet in the `assertions_kind_check` constraint; the loader synthesises these from
    # `withdrawn_at`.
    WITHDRAW = "withdraw"


class SourceRecord(BaseModel, frozen=True):
    id: str
    changeset_id: str
    created_at: datetime
    # Who the matcher said this is. A column on the row from step 6; until then
    # `database/facts.py` joins `source_record_identities` to fill it.
    person_id: str
    organization_id: str
    name: str
    label: str
    source_url: str
    other_names: tuple[str, ...] = ()
    url: str | None = None
    phone: str | None = None
    email: str | None = None
    image: str | None = None
    cdn_image: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class Claim(BaseModel, frozen=True):
    """What a user said about one thing, once.

    `field_path` is None only on a withdraw, which names a whole fact rather than a field.
    """

    id: str
    changeset_id: str | None
    created_at: datetime
    entity_type: EntityType
    entity_id: str
    field_path: str | None
    kind: ClaimKind
    value: Any


class SourcePage(BaseModel, frozen=True):
    id: str
    changeset_id: str
    created_at: datetime
    organization_ids: tuple[str, ...]


class Facts(BaseModel, frozen=True):
    records: tuple[SourceRecord, ...] = ()
    claims: tuple[Claim, ...] = ()
    withdraws: tuple[Claim, ...] = ()
    reads: tuple[SourcePage, ...] = ()


def latest_first(fact: SourceRecord | Claim) -> tuple[datetime, str]:
    """The one total order the whole fold means by "latest".

    `created_at` alone ties: `assertions` inserts with `clock_timestamp()` so a batch's claims
    differ, but `source_records` uses the column default, which is `now()` and therefore
    identical across a whole scrape. `id` is a random uuid, so the tiebreak is arbitrary but
    stable, which is what keeps two rebuilds of the same facts identical (R6).
    """
    return (fact.created_at, fact.id)
