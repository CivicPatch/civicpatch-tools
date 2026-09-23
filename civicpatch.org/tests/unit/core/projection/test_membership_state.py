"""What `membership_state` must answer.

An accept stands until withdrawn. A reject lasts until the organization is read again, and
then the page decides (2026-09-21). With no claim the latest read decides.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, PostKey, SourceRecord
from core.projection.memberships import membership_state

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
ALICE = {"alice"}
COUNCIL = "council"
MAYOR = PostKey(
    organization_id=COUNCIL,
    role_id="mayor",
    division_ocdid="ocd-division/country:us/state:tx/place:alpha",
)
CLERK = MAYOR.model_copy(update={"role_id": "clerk"})


def record(
    id: str, changeset: str, person: str = "alice", minutes: int = 0
) -> SourceRecord:
    """A page listed this person. `minutes` orders the reads."""
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=COUNCIL,
        name="Alice Ng",
        label="mayor",
        source_url="https://example.gov/council",
    )


def holds(
    id: str,
    post: PostKey = MAYOR,
    kind: ClaimKind = ClaimKind.ACCEPT,
    person: str = "alice",
    minutes: int = 0,
) -> Claim:
    """Somebody said this person holds this post: a claim about them, one per post."""
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.PERSON,
        entity_id=person,
        field_path="posts",
        kind=kind,
        value=post.post_id,
        post=post,
    )


@pytest.mark.unit
def test_nothing_known_means_no_membership():
    assert membership_state(ALICE, MAYOR, (), Facts()) is False


@pytest.mark.unit
def test_the_latest_read_listing_them_makes_it_live():
    own = (record("r1", "c1"),)
    facts = Facts(records=own)

    assert membership_state(ALICE, MAYOR, own, facts) is True


@pytest.mark.unit
def test_a_later_read_that_does_not_list_them_retires_them():
    """Nobody said Alice left. The council page was read again and she was not on it, which is
    the only thing that retires a scraped membership."""
    own = (record("r1", "c1", minutes=1),)
    facts = Facts(records=own + (record("r2", "c2", person="bob", minutes=2),))

    assert membership_state(ALICE, MAYOR, own, facts) is False


@pytest.mark.unit
def test_a_read_of_another_organization_retires_nobody():
    """The school board being read says nothing about who sits on the council."""
    own = (record("r1", "c1", minutes=1),)
    elsewhere = SourceRecord(
        id="r2",
        changeset_id="c2",
        created_at=_T + timedelta(minutes=2),
        person_id="bob",
        organization_id="school_board",
        name="Bob",
        label="member",
        source_url="https://example.gov/schools",
    )

    facts = Facts(records=own + (elsewhere,))

    assert membership_state(ALICE, MAYOR, own, facts) is True


@pytest.mark.unit
def test_an_exists_claim_holds_it_open_with_no_records_at_all():
    """A hand-assignment. No page ever said this, and it still has to project."""
    facts = Facts(claims=(holds("k1"),))

    assert membership_state(ALICE, MAYOR, (), facts) is True


@pytest.mark.unit
def test_an_accept_stands_when_a_later_read_omits_them():
    """A hand-add brought its own source; a page that never listed them has nothing to say."""
    facts = Facts(
        records=(record("r1", "c1", person="bob", minutes=3),),
        claims=(holds("k1", minutes=1),),
    )

    assert membership_state(ALICE, MAYOR, (), facts) is True


@pytest.mark.unit
def test_a_reject_ends_it():
    own = (record("r1", "c1", minutes=1),)
    facts = Facts(
        records=own, claims=(holds("k1", kind=ClaimKind.REJECT, minutes=2),)
    )

    assert membership_state(ALICE, MAYOR, own, facts) is False


@pytest.mark.unit
def test_a_later_read_listing_them_reinstates_them_over_a_reject():
    """The page wins at the next read."""
    own = (record("r1", "c1", minutes=1), record("r2", "c2", minutes=3))
    facts = Facts(
        records=own, claims=(holds("k1", kind=ClaimKind.REJECT, minutes=2),)
    )

    assert membership_state(ALICE, MAYOR, own, facts) is True


@pytest.mark.unit
def test_accepting_after_a_reject_reopens_it():
    """A re-election, and the only thing that reopens a rejected membership."""
    facts = Facts(
        claims=(
            holds("k1", kind=ClaimKind.REJECT, minutes=1),
            holds("k2", minutes=2),
        )
    )

    assert membership_state(ALICE, MAYOR, (), facts) is True


@pytest.mark.unit
def test_rejecting_after_an_accept_ends_it():
    """The same two claims the other way round: the newest wins."""
    facts = Facts(
        claims=(
            holds("k1", minutes=1),
            holds("k2", kind=ClaimKind.REJECT, minutes=2),
        )
    )

    assert membership_state(ALICE, MAYOR, (), facts) is False


@pytest.mark.unit
def test_a_claim_on_either_half_of_a_merge_counts():
    facts = Facts(claims=(holds("k1", person="alice2"),))

    assert membership_state({"alice", "alice2"}, MAYOR, (), facts) is True


@pytest.mark.unit
def test_a_claim_about_another_post_is_ignored():
    """The claim names the clerk's post, so it says nothing about this one."""
    other = holds("k1", CLERK, kind=ClaimKind.REJECT)
    own = (record("r1", "c1"),)

    assert membership_state(ALICE, MAYOR, own, Facts(records=own, claims=(other,))) is True


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6: the same facts rebuild the same projection, whatever order the loader returns."""
    own = (record("r1", "c1", minutes=1), record("r2", "c2", minutes=3))
    claims = (
        holds("k1", kind=ClaimKind.REJECT, minutes=2),
        holds("k2", minutes=4),
    )

    forwards = Facts(records=own, claims=claims)
    backwards = Facts(records=tuple(reversed(own)), claims=tuple(reversed(claims)))

    assert membership_state(ALICE, MAYOR, own, forwards) == membership_state(
        ALICE, MAYOR, tuple(reversed(own)), backwards
    )
