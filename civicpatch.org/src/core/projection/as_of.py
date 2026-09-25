"""Facts as they stood at a moment, cut in Python so history loads once and folds many times.

The same cut the loader makes in SQL (`database/facts.py`): a fact counts once its changeset
published, a claim with no changeset once it was made, and a withdraw always.

Identity is the exception. A merge or a split says who a person always was, so it applies to
every moment: history then shows one person where a merge says there is one.
"""

from collections.abc import Mapping
from datetime import datetime

from core.projection.canonical_ids import SAME_AS
from core.projection.facts import Claim, Facts
from core.projection.person_ids import PERSON_ID

_IDENTITY_FIELDS = (SAME_AS, PERSON_ID)


def facts_as_of(facts: Facts, published_at: Mapping[str, datetime], at: datetime) -> Facts:
    """`published_at` maps each changeset the facts name to when it published."""

    def counts(changeset_id: str | None, made_at: datetime) -> bool:
        if changeset_id is None:
            return made_at <= at
        published = published_at.get(changeset_id)
        return published is not None and published <= at

    def claim_counts(claim: Claim) -> bool:
        return claim.field_path in _IDENTITY_FIELDS or counts(claim.changeset_id, claim.created_at)

    return facts.model_copy(
        update={
            "records": tuple(
                record for record in facts.records if counts(record.changeset_id, record.created_at)
            ),
            "claims": tuple(claim for claim in facts.claims if claim_counts(claim)),
        }
    )


def _observed_at(facts: Facts) -> dict[str, datetime]:
    """Each changeset's earliest fact: when a scrape read the page, when an edit was made."""
    observed: dict[str, datetime] = {}
    for fact in (*facts.records, *facts.claims, *facts.withdraws):
        if fact.changeset_id is not None:
            observed[fact.changeset_id] = min(fact.created_at, observed.get(fact.changeset_id, fact.created_at))
    return observed


def snapshot_times(
    facts: Facts, published_at: Mapping[str, datetime]
) -> list[tuple[datetime, datetime]]:
    """`(cut, stamp)` for every publish, in publish order.

    Cut on `published_at`, since that is when a changeset's facts start to count; stamped with
    when its facts were observed, so review lag does not move a date. Changesets publishing
    together take the earliest observation, and a stamp never goes back: a row must not close
    before it opened. A claim with no changeset makes no moment of its own (step 16 ends them).
    """
    observed_at = _observed_at(facts)
    earliest: dict[datetime, datetime] = {}
    for changeset_id, cut in published_at.items():
        observed = observed_at.get(changeset_id, cut)
        earliest[cut] = min(observed, earliest.get(cut, observed))

    times: list[tuple[datetime, datetime]] = []
    for cut in sorted(earliest):
        stamp = earliest[cut] if not times else max(times[-1][1], earliest[cut])
        times.append((cut, stamp))
    return times
