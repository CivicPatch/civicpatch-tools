"""What `claimed_posts` must answer.

Scenario 20 of the simulator: a post is hand-assigned, then every record that mentioned it is
withdrawn, and the person must still hold it. That is the case a registry of posts built from
records cannot serve, and the reason an `exists` claim carries its post as its value.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.utils.membership_ids import membership_id

from core.projection.facts import Claim, ClaimKind, EntityType, Facts
from core.projection.memberships import claimed_posts

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
ALICE = {"alice"}
MAYOR = "council:mayor"
MEMBER = "council:member"


def exists(
    id: str,
    post: str,
    person: str = "alice",
    kind: ClaimKind = ClaimKind.ACCEPT,
    minutes: int = 0,
) -> Claim:
    """Alice holds `post`. The value is the post id, which is how the claim locates itself."""
    return Claim(
        id=id,
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id(person, post),
        field_path="exists",
        kind=kind,
        value=post,
    )


@pytest.mark.unit
def test_nobody_claimed_anything():
    assert claimed_posts(ALICE, Facts()) == set()


@pytest.mark.unit
def test_an_accepted_membership_names_its_post():
    facts = Facts(claims=(exists("k1", MAYOR),))

    assert claimed_posts(ALICE, facts) == {MAYOR}


@pytest.mark.unit
def test_a_rejected_membership_names_its_post_too():
    """The post is known either way. Whether the pair is live is `membership_state`'s call,
    and it cannot make it about a post nobody told it existed."""
    facts = Facts(claims=(exists("k1", MAYOR, kind=ClaimKind.REJECT),))

    assert claimed_posts(ALICE, facts) == {MAYOR}


@pytest.mark.unit
def test_several_posts_come_back_together():
    facts = Facts(claims=(exists("k1", MAYOR), exists("k2", MEMBER, minutes=1)))

    assert claimed_posts(ALICE, facts) == {MAYOR, MEMBER}


@pytest.mark.unit
def test_another_persons_membership_is_ignored():
    """`membership_id("bob", MAYOR)` matches no member of this cluster, so the hash test fails
    and the post is not theirs."""
    facts = Facts(claims=(exists("k1", MAYOR, person="bob"),))

    assert claimed_posts(ALICE, facts) == set()


@pytest.mark.unit
def test_a_claim_on_either_half_of_a_merge_counts():
    facts = Facts(claims=(exists("k1", MAYOR, person="alice2"),))

    assert claimed_posts({"alice", "alice2"}, facts) == {MAYOR}


@pytest.mark.unit
def test_a_claim_about_another_field_names_no_post():
    """Only `exists` carries a post as its value. A `closed` claim's value is true, and
    `membership_id(member, True)` matches nothing."""
    closed = Claim(
        id="k1",
        changeset_id="c1",
        created_at=_T,
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id("alice", MAYOR),
        field_path="closed",
        kind=ClaimKind.ACCEPT,
        value=True,
    )

    assert claimed_posts(ALICE, Facts(claims=(closed,))) == set()


@pytest.mark.unit
def test_a_claim_about_the_person_is_not_a_membership():
    person_claim = Claim(
        id="k1",
        changeset_id="c1",
        created_at=_T,
        entity_type=EntityType.PERSON,
        entity_id="alice",
        field_path="exists",
        kind=ClaimKind.ACCEPT,
        value=MAYOR,
    )

    assert claimed_posts(ALICE, Facts(claims=(person_claim,))) == set()


@pytest.mark.unit
def test_a_claim_whose_hash_does_not_match_its_value_is_ignored():
    """The route mints `entity_id` and the fold recomputes it. If the two encodings ever
    disagree the claim resolves against nothing, which is the failure this guards."""
    mismatched = Claim(
        id="k1",
        changeset_id="c1",
        created_at=_T,
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id("alice", MAYOR),
        field_path="exists",
        kind=ClaimKind.ACCEPT,
        value=MEMBER,
    )

    assert claimed_posts(ALICE, Facts(claims=(mismatched,))) == set()
