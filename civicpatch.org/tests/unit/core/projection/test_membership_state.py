"""What `membership_state` must answer.

Three rows: the newest live `exists` claim decides (accept holds it, reject does not), and with
no claim the latest read of the organization does. Everything here is one of the three rows,
or the boundary between two of them.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.utils.membership_ids import membership_id

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord
from core.projection.memberships import LISTED_AFTER_REJECT, membership_state

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
ALICE = {"alice"}
COUNCIL = "council"
MAYOR = "post-mayor"


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


def membership_claim(
    id: str,
    field: str,
    value,
    kind: ClaimKind = ClaimKind.ACCEPT,
    person: str = "alice",
    minutes: int = 0,
) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id(person, MAYOR),
        field_path=field,
        kind=kind,
        value=value,
    )


@pytest.mark.unit
def test_nothing_known_means_no_membership():
    assert membership_state(ALICE, MAYOR, (), Facts()).active is False


@pytest.mark.unit
def test_the_latest_read_listing_them_makes_it_live():
    own = (record("r1", "c1"),)
    facts = Facts(records=own)

    assert membership_state(ALICE, MAYOR, own, facts).active is True


@pytest.mark.unit
def test_a_later_read_that_does_not_list_them_retires_them():
    """Nobody said Alice left. The council page was read again and she was not on it, which is
    the only thing that retires a scraped membership."""
    own = (record("r1", "c1", minutes=1),)
    facts = Facts(records=own + (record("r2", "c2", person="bob", minutes=2),))

    assert membership_state(ALICE, MAYOR, own, facts).active is False


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

    assert membership_state(ALICE, MAYOR, own, facts).active is True


@pytest.mark.unit
def test_an_exists_claim_holds_it_open_with_no_records_at_all():
    """A hand-assignment. No page ever said this, and it still has to project."""
    facts = Facts(claims=(membership_claim("k1", "exists", MAYOR),))

    assert membership_state(ALICE, MAYOR, (), facts).active is True


@pytest.mark.unit
def test_an_exists_reject_suppresses_it_however_often_the_page_says_otherwise():
    """The scraper keeps mislabelling this person. The reject outlives every re-scrape, which
    is what makes it different from withdrawing the record."""
    own = (record("r1", "c1"),)
    facts = Facts(
        records=own,
        claims=(membership_claim("k1", "exists", MAYOR, kind=ClaimKind.REJECT),),
    )

    assert membership_state(ALICE, MAYOR, own, facts).active is False


@pytest.mark.unit
def test_a_reject_ends_it():
    own = (record("r1", "c1", minutes=1),)
    facts = Facts(
        records=own, claims=(membership_claim("k1", "exists", MAYOR, kind=ClaimKind.REJECT, minutes=2),)
    )

    assert membership_state(ALICE, MAYOR, own, facts).active is False


@pytest.mark.unit
def test_a_reject_stands_even_while_the_page_keeps_listing_them():
    """No evidence reopens a reject: a stale page must not undo a human's "they are gone". The
    issue is what prompts somebody to look again."""
    own = (record("r1", "c1", minutes=1), record("r2", "c2", minutes=3))
    facts = Facts(
        records=own, claims=(membership_claim("k1", "exists", MAYOR, kind=ClaimKind.REJECT, minutes=2),)
    )

    state = membership_state(ALICE, MAYOR, own, facts)

    assert state.active is False
    assert state.issue == LISTED_AFTER_REJECT


@pytest.mark.unit
def test_a_reject_the_page_agrees_with_raises_nothing():
    own = (record("r1", "c1", minutes=1),)
    facts = Facts(
        records=own + (record("r2", "c2", person="bob", minutes=3),),
        claims=(membership_claim("k1", "exists", MAYOR, kind=ClaimKind.REJECT, minutes=2),),
    )

    state = membership_state(ALICE, MAYOR, own, facts)

    assert state.active is False
    assert state.issue is None


@pytest.mark.unit
def test_accepting_after_a_reject_reopens_it():
    """A re-election, and the only thing that reopens a rejected membership."""
    facts = Facts(
        claims=(
            membership_claim("k1", "exists", MAYOR, kind=ClaimKind.REJECT, minutes=1),
            membership_claim("k2", "exists", MAYOR, minutes=2),
        )
    )

    assert membership_state(ALICE, MAYOR, (), facts).active is True


@pytest.mark.unit
def test_rejecting_after_an_accept_ends_it():
    """The same two claims the other way round: the newest wins."""
    facts = Facts(
        claims=(
            membership_claim("k1", "exists", MAYOR, minutes=1),
            membership_claim("k2", "exists", MAYOR, kind=ClaimKind.REJECT, minutes=2),
        )
    )

    assert membership_state(ALICE, MAYOR, (), facts).active is False


@pytest.mark.unit
def test_a_claim_on_either_half_of_a_merge_counts():
    facts = Facts(claims=(membership_claim("k1", "exists", MAYOR, person="alice2"),))

    assert membership_state({"alice", "alice2"}, MAYOR, (), facts).active is True


@pytest.mark.unit
def test_a_claim_about_another_post_is_ignored():
    """The claim is addressed to `uuid5(alice, some other post)`, so it is not about this
    membership at all."""
    other = Claim(
        id="k1",
        changeset_id="c9",
        created_at=_T,
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id("alice", "post-clerk"),
        field_path="exists",
        kind=ClaimKind.REJECT,
        value="post-clerk",
    )
    own = (record("r1", "c1"),)

    assert membership_state(ALICE, MAYOR, own, Facts(records=own, claims=(other,))).active is True


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6: the same facts rebuild the same projection, whatever order the loader returns."""
    own = (record("r1", "c1", minutes=1), record("r2", "c2", minutes=3))
    claims = (
        membership_claim("k1", "exists", MAYOR, kind=ClaimKind.REJECT, minutes=2),
        membership_claim("k2", "exists", MAYOR, minutes=4),
    )

    forwards = Facts(records=own, claims=claims)
    backwards = Facts(records=tuple(reversed(own)), claims=tuple(reversed(claims)))

    assert membership_state(ALICE, MAYOR, own, forwards) == membership_state(
        ALICE, MAYOR, tuple(reversed(own)), backwards
    )
