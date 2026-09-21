"""What `canonical_ids` must answer.

The cases are scenarios 6, 24 and 25 of `.scratch/2026-09-19-rollback-simulator.html`: a merge,
a chain with its middle unmerged, and the rule that decides which id a cluster shows under.

Every read is `.get(person_id, person_id)` because that is how the fold reads it: an id nobody
merged does not appear, and is its own answer.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.canonical_ids import canonical_ids
from core.projection.facts import Claim, ClaimKind, EntityType

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def same_as(id: str, person: str, other: str, minutes: int = 0) -> Claim:
    """`person` is the same as `other`. `minutes` orders the claims."""
    return Claim(
        id=id,
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.PERSON,
        entity_id=person,
        field_path="same_as",
        kind=ClaimKind.ACCEPT,
        value=other,
    )


@pytest.mark.unit
def test_with_no_claims_nobody_is_merged():
    assert canonical_ids([]) == {}


@pytest.mark.unit
def test_a_merge_puts_both_under_the_target():
    """Scenario 6: merging a1 into a2 shows the cluster under a2, the id merged into."""
    canonical = canonical_ids([same_as("k1", "a1", "a2")])

    assert canonical.get("a1", "a1") == "a2"
    assert canonical.get("a2", "a2") == "a2"


@pytest.mark.unit
def test_a_chain_resolves_to_the_far_end():
    """Scenario 24: a -> b then b -> c is one person, known by c."""
    canonical = canonical_ids(
        [same_as("k1", "a", "b", minutes=1), same_as("k2", "b", "c", minutes=2)]
    )

    assert canonical.get("a", "a") == "c"
    assert canonical.get("b", "b") == "c"
    assert canonical.get("c", "c") == "c"


@pytest.mark.unit
def test_unmerging_the_middle_leaves_the_rest_merged():
    """Scenario 24 again: the b -> c claim is withdrawn, so this never sees it. a and b stay
    together because their own claim is untouched; nothing was rewritten to undo it."""
    canonical = canonical_ids([same_as("k1", "a", "b", minutes=1)])

    assert canonical.get("a", "a") == "b"
    assert canonical.get("c", "c") == "c"


@pytest.mark.unit
def test_two_clusters_merge_whole_not_pairwise():
    """a-b and c-d are two clusters; merging b into c must bring a and d together too."""
    canonical = canonical_ids(
        [
            same_as("k1", "a", "b", minutes=1),
            same_as("k2", "c", "d", minutes=2),
            same_as("k3", "b", "c", minutes=3),
        ]
    )

    assert canonical.get("a", "a") == canonical.get("d", "d") == "d"


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_claims_arrive():
    """R6: the same facts rebuild the same projection, whatever order the loader returns them."""
    claims = [
        same_as("k1", "a", "b", minutes=1),
        same_as("k2", "c", "d", minutes=2),
        same_as("k3", "b", "c", minutes=3),
    ]

    assert canonical_ids(claims) == canonical_ids(list(reversed(claims)))


@pytest.mark.unit
def test_a_person_merged_into_twice_ends_up_in_one_cluster():
    """Two people merged into the same target: one cluster, not two."""
    canonical = canonical_ids(
        [same_as("k1", "a", "c", minutes=1), same_as("k2", "b", "c", minutes=2)]
    )

    assert canonical.get("a", "a") == canonical.get("b", "b") == "c"


@pytest.mark.unit
def test_a_root_does_not_map_to_itself():
    """Only merged ids appear, so the dict says what changed and nothing else."""
    canonical = canonical_ids([same_as("k1", "a", "b")])

    assert canonical == {"a": "b"}


@pytest.mark.unit
def test_a_claim_pointing_at_itself_does_not_hang():
    """Not a thing the UI can file, but the fold must not spin on a fact it is handed."""
    assert canonical_ids([same_as("k1", "a", "a")]) == {}
