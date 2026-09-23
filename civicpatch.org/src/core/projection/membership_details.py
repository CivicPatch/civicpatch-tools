"""What a membership's own records say about it, beyond which post it is.

Ported from `core/post_derivation.py`, which deploy B deletes.
"""

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel
from shared.schemas import Role
from shared.utils.taxonomy import Taxonomy

from core.people_roles import derive_roles
from core.projection.facts import Claim, SourceRecord, latest_first


class MembershipSource(BaseModel, frozen=True):
    note: str | None = None
    url: str | None = None


class LabelDetails(BaseModel, frozen=True):
    designations: tuple[str, ...] = ()
    unmatched_text: tuple[str, ...] = ()
    # Role ids beyond the post's own, for `membership_roles`.
    extra_roles: tuple[str, ...] = ()


def first_seen(facts: Sequence[SourceRecord | Claim]) -> datetime:
    return min(fact.created_at for fact in facts)


def last_seen(facts: Sequence[SourceRecord | Claim]) -> datetime:
    return max(fact.created_at for fact in facts)


def membership_sources(records: Sequence[SourceRecord]) -> tuple[MembershipSource, ...]:
    pairs = dict.fromkeys(
        (record.label, record.source_url)
        for record in sorted(records, key=latest_first)
    )
    return tuple(MembershipSource(note=label, url=url) for label, url in pairs)


def label_details(
    records: Sequence[SourceRecord],
    jurisdiction_ocdid: str,
    taxonomy: Taxonomy,
    roles: Sequence[Role],
) -> LabelDetails:
    labels = list(
        dict.fromkeys(record.label for record in sorted(records, key=latest_first))
    )
    parsed = derive_roles(labels, jurisdiction_ocdid, taxonomy)

    ids_by_label = {role.label: role.id for role in roles}
    winner_id = ids_by_label.get(parsed.role) if parsed.role else None
    extra_roles = [
        ids_by_label[label]
        for label in parsed.roles
        if label in ids_by_label and ids_by_label[label] != winner_id
    ]
    unmatched_text = dict.fromkeys(
        term
        for part in parsed.parts
        if not part.parsed.role
        for term in part.parsed.unmatched
    )

    return LabelDetails(
        designations=tuple(parsed.other_designations),
        unmatched_text=tuple(unmatched_text),
        extra_roles=tuple(extra_roles),
    )
