"""What `claimed_posts` must answer.

Scenario 20 of the simulator: a post is hand-assigned, then every record that mentioned it is
withdrawn, and the person must still hold it. That is the case a set of posts built from
records alone cannot serve, and the reason the claim names its post.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, PostKey
from core.projection.memberships import claimed_posts

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
ALICE = {"alice"}
COUNCIL = "11111111-1111-1111-1111-111111111111"
BASE = "ocd-division/country:us/state:tx/place:alpha"
MAYOR = PostKey(organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE)
MEMBER = PostKey(organization_id=COUNCIL, role_id="council-member", division_ocdid=BASE)


def holds(
    id: str,
    post: PostKey,
    person: str = "alice",
    kind: ClaimKind = ClaimKind.ACCEPT,
    minutes: int = 0,
) -> Claim:
    """Alice holds `post`: a claim about her, one per post. The stored value is the post's
    id, and the loader resolves the key the fold reads."""
    return Claim(
        id=id,
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.PERSON,
        entity_id=person,
        field_path="posts",
        kind=kind,
        value=post.post_id,
        post=post,
    )


@pytest.mark.unit
def test_nobody_claimed_anything():
    assert claimed_posts(ALICE, Facts()) == set()


@pytest.mark.unit
def test_an_accepted_post_is_named():
    facts = Facts(claims=(holds("k1", MAYOR),))

    assert claimed_posts(ALICE, facts) == {MAYOR}


@pytest.mark.unit
def test_a_rejected_post_is_named_too():
    """The post is known either way. Whether they hold it is `membership_state`'s call, and it
    cannot make it about a post nobody told it existed."""
    facts = Facts(claims=(holds("k1", MAYOR, kind=ClaimKind.REJECT),))

    assert claimed_posts(ALICE, facts) == {MAYOR}


@pytest.mark.unit
def test_several_posts_come_back_together():
    facts = Facts(claims=(holds("k1", MAYOR), holds("k2", MEMBER, minutes=1)))

    assert claimed_posts(ALICE, facts) == {MAYOR, MEMBER}


@pytest.mark.unit
def test_another_persons_post_is_ignored():
    facts = Facts(claims=(holds("k1", MAYOR, person="bob"),))

    assert claimed_posts(ALICE, facts) == set()


@pytest.mark.unit
def test_a_claim_on_either_half_of_a_merge_counts():
    facts = Facts(claims=(holds("k1", MAYOR, person="alice2"),))

    assert claimed_posts({"alice", "alice2"}, facts) == {MAYOR}


@pytest.mark.unit
def test_a_claim_about_another_field_names_no_post():
    """Only `posts` says which posts they hold. Every other claim about a person is about the
    person."""
    name = Claim(
        id="k1",
        changeset_id="c1",
        created_at=_T,
        entity_type=EntityType.PERSON,
        entity_id="alice",
        field_path="name",
        kind=ClaimKind.ACCEPT,
        value="Ana Reyes",
    )

    assert claimed_posts(ALICE, Facts(claims=(name,))) == set()


@pytest.mark.unit
def test_a_claim_about_the_membership_names_no_post():
    """A membership claim is about what the membership is called, not whether it is there —
    and it is keyed by the membership's id, which says nothing the fold can read back."""
    label = Claim(
        id="k1",
        changeset_id="c1",
        created_at=_T,
        entity_type=EntityType.MEMBERSHIP,
        entity_id="alice",
        field_path="label",
        kind=ClaimKind.ACCEPT,
        value="Mayor (interim)",
    )

    assert claimed_posts(ALICE, Facts(claims=(label,))) == set()
