"""Claims on fields the page owns hold only until the page is read again.

A claim on a temporary field goes stale once every current record of its person is newer
than it: the page has been re-read, so its answer wins. Every other claim holds until withdrawn.
"""

from collections.abc import Iterable
from datetime import datetime

from core.people_edits import POSTS_FIELD
from core.projection.facts import Claim, EntityType, Facts
from core.projection.field_value import current_records

TEMPORARY_FIELDS: frozenset[tuple[EntityType, str]] = frozenset({(EntityType.PERSON, POSTS_FIELD)})


def without_stale_claims(members: Iterable[str], facts: Facts) -> Facts:
    """`facts` as one cluster's derivation sees them."""
    records = current_records(members, facts)
    if not records:
        return facts
    oldest_read = min(record.created_at for record in records)
    return facts.model_copy(
        update={"claims": tuple(c for c in facts.claims if not _stale(c, oldest_read))}
    )


def _stale(claim: Claim, oldest_read: datetime) -> bool:
    is_temporary = (claim.entity_type, claim.field_path) in TEMPORARY_FIELDS
    return is_temporary and claim.created_at < oldest_read
