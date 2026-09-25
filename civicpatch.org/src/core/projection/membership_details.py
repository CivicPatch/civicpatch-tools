"""What a membership's own records say about it, beyond which post it is.

`LabelDetails` is filled by `posts.parse_labels`, which reads the labels once for both
answers. Ported from `core/post_derivation.py`, which deploy B deletes.
"""

from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel

from core.projection.facts import Claim, SourceRecord, latest_first


class MembershipSource(BaseModel, frozen=True):
    note: str | None = None
    url: str | None = None


class LabelDetails(BaseModel, frozen=True):
    designations: tuple[str, ...] = ()
    unmatched_text: tuple[str, ...] = ()
    # Role ids beyond the post's own; not stored, they feed the membership label (10a).
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
