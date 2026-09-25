import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from shared.utils.statuses import ClaimKind, EntityType

POST_NAMESPACE = uuid.UUID("c8374c67-da4d-4aac-a0d9-4f353c803eca")


class PostKey(BaseModel, frozen=True):
    """A post, as the fold names one: `(organization, role, division)`.

    Lives with the facts because a claim about a post carries one, and because the fold has to
    be able to say which organization a membership is in without reading `posts`.
    """

    organization_id: str
    role_id: str
    division_ocdid: str

    @property
    def post_id(self) -> str:
        return str(
            uuid.uuid5(
                POST_NAMESPACE,
                f"{self.organization_id}|{self.role_id}|{self.division_ocdid}",
            )
        )


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
    # This source stated only the cells it filled, so a blank here is no information and keeps
    # the last stated value. A scrape reads a whole page, so its blank is a clearing.
    is_partial: bool = False


class Claim(BaseModel, frozen=True):
    """What a user said about one thing, once.

    `field_path` is None only on a withdraw, which names a whole fact rather than a field.
    `post` is the post a `posts` claim's value names, which the loader resolves: the value is
    stored as the post's id, and the fold works in keys.
    """

    id: str
    changeset_id: str | None
    created_at: datetime
    entity_type: EntityType
    entity_id: str
    field_path: str | None
    kind: ClaimKind
    value: Any
    post: PostKey | None = None


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

    `created_at` alone ties: `claims` inserts with `clock_timestamp()` so a batch's claims
    differ, but `source_records` uses the column default, which is `now()` and therefore
    identical across a whole scrape. `id` is a random uuid, so the tiebreak is arbitrary but
    stable, which is what keeps two rebuilds of the same facts identical (R6).
    """
    return (fact.created_at, fact.id)
