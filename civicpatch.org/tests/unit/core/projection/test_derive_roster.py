"""What `derive_roster` must answer.

It only chains resolvers that have their own tests, so these cases are the joins: that each
step's output is the next step's input, and that the order they run in is the right one.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.membership_ids import membership_id
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, PostKey, SourceRecord
from core.projection.roster import derive_roster

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
BASE = "ocd-division/country:us/state:tx/place:alpha"
COUNCIL = "council"

ROLES = [
    Role(
        id="mayor", label="Mayor", status=RoleStatus.ACTIVE, aliases=[], priority=10,
        is_unique=False,
    ),
]
TAXONOMY = build_taxonomy(RoleConfig(roles=ROLES))
MAYOR_KEY = PostKey(organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE)
MAYOR = MAYOR_KEY.post_id


def record(id: str, person: str, name: str = "Someone", minutes: int = 0) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=COUNCIL,
        name=name,
        label="Mayor",
        source_url="https://example.gov/council",
    )


def claim(
    id: str,
    entity_type: EntityType,
    entity_id: str,
    field: str | None,
    value,
    kind: ClaimKind = ClaimKind.ACCEPT,
    minutes: int = 0,
) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=entity_type,
        entity_id=entity_id,
        field_path=field,
        kind=kind,
        value=value,
    )


def withdraw(id: str, target: str, entity_type: EntityType) -> Claim:
    return claim(id, entity_type, target, None, None, kind=ClaimKind.WITHDRAW)


def derive(facts: Facts):
    return derive_roster(facts, JURISDICTION, TAXONOMY, ROLES)


def ids(roster):
    return [person.id for person in roster.people]


@pytest.mark.unit
def test_no_facts_no_people():
    assert derive(Facts()).people == ()


@pytest.mark.unit
def test_each_person_a_record_names_is_on_the_roster():
    facts = Facts(records=(record("r1", "alice"), record("r2", "bob")))

    assert ids(derive(facts)) == ["alice", "bob"]


@pytest.mark.unit
def test_people_come_back_sorted_by_id():
    """R6: the loader's order must not leak into the output."""
    facts = Facts(records=(record("r1", "carol"), record("r2", "alice"), record("r3", "bob")))

    assert ids(derive(facts)) == ["alice", "bob", "carol"]


@pytest.mark.unit
def test_withdrawn_facts_do_not_count():
    """`live_facts` runs first. Withdraw Bob's only record and Bob is gone."""
    facts = Facts(
        records=(record("r1", "alice"), record("r2", "bob")),
        withdraws=(withdraw("w1", "r2", EntityType.SOURCE_RECORD),),
    )

    assert ids(derive(facts)) == ["alice"]


@pytest.mark.unit
def test_a_split_moves_the_record_before_anyone_is_grouped():
    """`with_person_ids` runs before clustering. The record matched to Alice is really Bob's,
    so Bob exists and Alice, who had nothing else, does not."""
    facts = Facts(
        records=(record("r1", "alice", name="Bob Lee"),),
        claims=(claim("k1", EntityType.SOURCE_RECORD, "r1", "person_id", "bob"),),
    )

    roster = derive(facts)

    assert ids(roster) == ["bob"]
    assert roster.people[0].name == "Bob Lee"


@pytest.mark.unit
def test_a_merge_is_one_person_under_the_target():
    facts = Facts(
        records=(record("r1", "alice", minutes=1), record("r2", "alice2", minutes=2)),
        claims=(claim("k1", EntityType.PERSON, "alice", "same_as", "alice2"),),
    )

    assert ids(derive(facts)) == ["alice2"]


@pytest.mark.unit
def test_withdrawing_a_merge_splits_them_again():
    """Scenario 6: the unmerge is a withdraw of the `same_as` claim, and nothing is rewritten."""
    facts = Facts(
        records=(record("r1", "alice", minutes=1), record("r2", "alice2", minutes=2)),
        claims=(claim("k1", EntityType.PERSON, "alice", "same_as", "alice2"),),
        withdraws=(withdraw("w1", "k1", EntityType.CLAIM),),
    )

    assert ids(derive(facts)) == ["alice", "alice2"]


@pytest.mark.unit
def test_a_person_claim_with_no_record_is_a_hand_added_person():
    facts = Facts(claims=(claim("k1", EntityType.PERSON, "dana", "name", "Dana Ruiz"),))

    roster = derive(facts)

    assert ids(roster) == ["dana"]
    assert roster.people[0].name == "Dana Ruiz"


@pytest.mark.unit
def test_a_claim_on_the_merge_target_counts_when_no_record_names_the_target():
    """Alice was merged into alice2, and only Alice has records. A membership claim filed on
    alice2 has to reach the cluster, which it only does if the target itself is a member."""
    facts = Facts(
        records=(record("r1", "alice"),),
        claims=(
            claim("k1", EntityType.PERSON, "alice", "same_as", "alice2"),
            claim(
                "k2",
                EntityType.MEMBERSHIP,
                membership_id("alice2", MAYOR),
                "label",
                "Mayor (interim)",
            ),
        ),
    )

    roster = derive(facts)

    assert ids(roster) == ["alice2"]
    assert roster.people[0].memberships[0].label == "Mayor (interim)"


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6."""
    records = (record("r1", "alice", minutes=1), record("r2", "bob", minutes=2))
    claims = (
        claim("k1", EntityType.PERSON, "alice", "name", "Alice Ng", minutes=3),
        claim("k2", EntityType.PERSON, "bob", "same_as", "carol", minutes=4),
    )

    forwards = derive(Facts(records=records, claims=claims))
    backwards = derive(Facts(records=tuple(reversed(records)), claims=tuple(reversed(claims))))

    assert forwards == backwards
