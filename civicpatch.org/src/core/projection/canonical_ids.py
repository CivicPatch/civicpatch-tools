"""Which person ids are really one person.

A merge is a claim: `same_as` on person A, valued B. Merging is transitive, so the claims form
a forest and "who is this really" is "walk to the root".

    same_as: a -> b,  same_as: b -> c    =>    {"a": "c", "b": "c"}

"""

from collections.abc import Iterable, Mapping
from datetime import datetime

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, latest_first

SAME_AS = "same_as"


def canonical_ids(same_as: Iterable[Claim]) -> dict[str, str]:
    """Every merged person id, mapped to the id its cluster is known by."""
    parent: dict[str, str] = {}

    def find(p):
        while p in parent and parent[p] != p:
            p = parent[p]
        return p

    for claim in sorted(same_as, key=latest_first):
        a = find(claim.entity_id)
        b = find(claim.value)
        if a != b:
            parent[a] = b

    return {person_id: find(person_id) for person_id in parent}


def with_merges(facts: Facts, merged_into: Mapping[str, str], at: datetime) -> Facts:
    """Facts as they will be once these merges are filed, so an edit can diff against them."""
    merges = tuple(
        Claim(
            id=f"{SAME_AS}:{absorbed_id}",
            changeset_id=None,
            created_at=at,
            entity_type=EntityType.PERSON,
            entity_id=absorbed_id,
            field_path=SAME_AS,
            kind=ClaimKind.ACCEPT,
            value=survivor_id,
        )
        for absorbed_id, survivor_id in sorted(merged_into.items())
    )
    return facts.model_copy(update={"claims": facts.claims + merges})


def without_merges(facts: Facts) -> Facts:
    """One person per base identity, which is all the matcher may link to (§8): a record linked
    to a merged cluster would land on the wrong half after an unmerge."""
    return facts.model_copy(
        update={"claims": tuple(claim for claim in facts.claims if claim.field_path != SAME_AS)}
    )
