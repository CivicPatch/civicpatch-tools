"""What `live_facts` must answer.

The cases are scenarios 1, 7 and 9 of `.scratch/2026-09-19-rollback-simulator.html`, which is
where this model's behaviour is specified and run.
"""

from datetime import datetime, timezone

import pytest

from core.projection.facts import (
    Claim,
    ClaimKind,
    EntityType,
    Facts,
    SourcePage,
    SourceRecord,
)
from core.projection.live_facts import live_facts

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def record(id: str) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id="c1",
        created_at=_T,
        person_id="alice",
        organization_id="council",
        name="Alice Ng",
        label="mayor",
        source_url="https://example.gov/council",
    )


def claim(id: str, value: str = "555-1111") -> Claim:
    return Claim(
        id=id,
        changeset_id="c1",
        created_at=_T,
        entity_type=EntityType.PERSON,
        entity_id="alice",
        field_path="phone",
        kind=ClaimKind.ACCEPT,
        value=value,
    )


def page(id: str) -> SourcePage:
    return SourcePage(
        id=id, changeset_id="c1", created_at=_T, organization_ids=("council",)
    )


def withdraw(id: str, entity_type: EntityType, target: str) -> Claim:
    return Claim(
        id=id,
        changeset_id="c2",
        created_at=_T,
        entity_type=entity_type,
        entity_id=target,
        field_path=None,
        kind=ClaimKind.WITHDRAW,
        value=None,
    )


def ids(facts: Facts) -> dict[str, list[str]]:
    return {
        "records": [r.id for r in facts.records],
        "claims": [c.id for c in facts.claims],
        "withdraws": [w.id for w in facts.withdraws],
        "reads": [p.id for p in facts.reads],
    }


@pytest.mark.unit
def test_with_no_withdraws_everything_is_live():
    facts = Facts(records=(record("r1"),), claims=(claim("k1"),), reads=(page("p1"),))

    assert ids(live_facts(facts)) == {
        "records": ["r1"],
        "claims": ["k1"],
        "withdraws": [],
        "reads": ["p1"],
    }


@pytest.mark.unit
def test_a_withdrawn_claim_is_dropped_and_its_withdraw_stays():
    facts = Facts(
        claims=(claim("k1"),),
        withdraws=(withdraw("w1", EntityType.PERSON, "k1"),),
    )

    live = live_facts(facts)

    assert ids(live)["claims"] == []
    assert ids(live)["withdraws"] == ["w1"], "a live withdraw is a live fact"


@pytest.mark.unit
def test_withdrawing_a_withdraw_brings_the_claim_back():
    """Scenario 1: the vandal's withdraw is rolled back, so the claim underneath counts again."""
    facts = Facts(
        claims=(claim("k1"),),
        withdraws=(
            withdraw("w1", EntityType.PERSON, "k1"),
            withdraw("w2", EntityType.PERSON, "w1"),
        ),
    )

    live = live_facts(facts)

    assert ids(live)["claims"] == ["k1"]
    assert ids(live)["withdraws"] == ["w2"], "w1 is dead, so only the rollback's own survives"


@pytest.mark.unit
def test_a_chain_three_deep_undoes_again():
    """Scenario 9: roll back, undo, roll back. Odd depth cancels, even depth restores."""
    facts = Facts(
        claims=(claim("k1"),),
        withdraws=(
            withdraw("w1", EntityType.PERSON, "k1"),
            withdraw("w2", EntityType.PERSON, "w1"),
            withdraw("w3", EntityType.PERSON, "w2"),
        ),
    )

    live = live_facts(facts)

    assert ids(live)["claims"] == [], "w3 kills w2, so w1 stands again"
    assert ids(live)["withdraws"] == ["w1", "w3"]


@pytest.mark.unit
def test_records_and_page_rows_are_withdrawable_too():
    """Scenario 7: rolling back a read that listed nobody has only its page row to withdraw."""
    facts = Facts(
        records=(record("r1"), record("r2")),
        reads=(page("p1"), page("p2")),
        withdraws=(
            withdraw("w1", EntityType.PERSON, "r2"),
            withdraw("w2", EntityType.PERSON, "p2"),
        ),
    )

    live = live_facts(facts)

    assert ids(live)["records"] == ["r1"]
    assert ids(live)["reads"] == ["p1"]


@pytest.mark.unit
def test_two_withdraws_of_one_fact_both_have_to_die_for_it_to_return():
    """Two admins roll back the same changeset; undoing one is not enough."""
    facts = Facts(
        claims=(claim("k1"),),
        withdraws=(
            withdraw("w1", EntityType.PERSON, "k1"),
            withdraw("w2", EntityType.PERSON, "k1"),
            withdraw("w3", EntityType.PERSON, "w1"),
        ),
    )

    assert ids(live_facts(facts))["claims"] == [], "w2 still points at it"


@pytest.mark.unit
def test_the_input_is_not_mutated():
    facts = Facts(
        claims=(claim("k1"),), withdraws=(withdraw("w1", EntityType.PERSON, "k1"),)
    )

    live_facts(facts)

    assert ids(facts)["claims"] == ["k1"]
