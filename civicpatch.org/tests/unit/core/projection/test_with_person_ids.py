"""What `with_person_ids` must answer.

Scenario 14 of the simulator: a record matched to the wrong person is split off, and the split
has to survive every later scrape. It survives because it is a claim on the record, and the
matcher never overwrites a claim.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord
from core.projection.person_ids import with_person_ids

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def record(id: str, person: str = "alice", minutes: int = 0) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id="council",
        name="Alice Ng",
        label="mayor",
        source_url="https://example.gov/council",
    )


def owner_claim(
    id: str, record_id: str, person: str, minutes: int = 0, kind: ClaimKind = ClaimKind.ACCEPT
) -> Claim:
    """This record is about `person`, whatever the matcher said."""
    return Claim(
        id=id,
        changeset_id="c2",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.SOURCE_RECORD,
        entity_id=record_id,
        field_path="person_id",
        kind=kind,
        value=person,
    )


@pytest.mark.unit
def test_a_record_nobody_claimed_keeps_the_matchers_answer():
    facts = Facts(records=(record("r1", person="alice"),))

    assert with_person_ids(facts).records[0].person_id == "alice"


@pytest.mark.unit
def test_a_claim_moves_the_record():
    facts = Facts(
        records=(record("r1", person="alice"),),
        claims=(owner_claim("k1", "r1", "bob"),),
    )

    assert with_person_ids(facts).records[0].person_id == "bob"


@pytest.mark.unit
def test_the_newest_claim_wins():
    facts = Facts(
        records=(record("r1", person="alice"),),
        claims=(
            owner_claim("k1", "r1", "bob", minutes=1),
            owner_claim("k2", "r1", "carol", minutes=2),
        ),
    )

    assert with_person_ids(facts).records[0].person_id == "carol"


@pytest.mark.unit
def test_only_the_claimed_record_moves():
    """The point of a split: the other records that matched the same way stay where they are."""
    facts = Facts(
        records=(record("r1", person="alice"), record("r2", person="alice", minutes=1)),
        claims=(owner_claim("k1", "r1", "bob"),),
    )

    moved = with_person_ids(facts).records

    assert [r.person_id for r in moved] == ["bob", "alice"]


@pytest.mark.unit
def test_a_claim_about_a_field_that_is_not_ownership_is_ignored():
    not_ownership = Claim(
        id="k1",
        changeset_id="c2",
        created_at=_T,
        entity_type=EntityType.SOURCE_RECORD,
        entity_id="r1",
        field_path="name",
        kind=ClaimKind.ACCEPT,
        value="bob",
    )

    facts = Facts(records=(record("r1", person="alice"),), claims=(not_ownership,))

    assert with_person_ids(facts).records[0].person_id == "alice"


@pytest.mark.unit
def test_a_person_claim_is_not_a_record_claim():
    """`entity_id` is a person id here, not a record id, and they must not collide."""
    person_claim = Claim(
        id="k1",
        changeset_id="c2",
        created_at=_T,
        entity_type=EntityType.PERSON,
        entity_id="r1",
        field_path="person_id",
        kind=ClaimKind.ACCEPT,
        value="bob",
    )

    facts = Facts(records=(record("r1", person="alice"),), claims=(person_claim,))

    assert with_person_ids(facts).records[0].person_id == "alice"


@pytest.mark.unit
def test_everything_else_is_handed_back_untouched():
    """Only records change. A claim is a fact, and rewriting one here would make the claims
    the fold reads differ from the claims that were filed."""
    claims = (owner_claim("k1", "r1", "bob"),)
    facts = Facts(records=(record("r1"),), claims=claims)

    result = with_person_ids(facts)

    assert result.claims == claims
    assert result.withdraws == ()
    assert result.reads == ()


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6."""
    records = (record("r1", minutes=1), record("r2", minutes=2))
    claims = (
        owner_claim("k1", "r1", "bob", minutes=3),
        owner_claim("k2", "r1", "carol", minutes=4),
    )

    forwards = with_person_ids(Facts(records=records, claims=claims))
    backwards = with_person_ids(
        Facts(records=records, claims=tuple(reversed(claims)))
    )

    assert forwards.records == backwards.records
