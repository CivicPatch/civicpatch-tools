"""Which person ids are really one person.

A merge is a claim: `same_as` on person A, valued B. Merging is transitive, so the claims form
a forest and "who is this really" is "walk to the root".

    same_as: a -> b,  same_as: b -> c    =>    {"a": "c", "b": "c"}

"""

from collections.abc import Iterable

from core.projection.facts import Claim, latest_first

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
