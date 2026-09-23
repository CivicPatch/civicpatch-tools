"""What `field_value` must answer.

Scalar cases come from scenarios 2, 3 and 15 of the simulator: a claim beats evidence, the
newest claim beats an older one, and withdrawing the newest reveals the one underneath.
The list cases come from today's `core/people_edits.with_asserted_values`, which is the
behaviour the fold has to keep.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord
from core.projection.field_value import list_value, scalar_value

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
ALICE = {"alice"}


def record(id: str, minutes: int = 0, **fields) -> SourceRecord:
    """One page's line about Alice. `minutes` orders the records."""
    return SourceRecord(
        id=id,
        changeset_id=fields.pop("changeset_id", "c1"),
        created_at=_T + timedelta(minutes=minutes),
        person_id=fields.pop("person_id", "alice"),
        organization_id=fields.pop("organization_id", "council"),
        name=fields.pop("name", "Alice Ng"),
        label="mayor",
        source_url="https://example.gov/council",
        **fields,
    )


def claim(
    id: str,
    field: str,
    value,
    kind: ClaimKind = ClaimKind.ACCEPT,
    minutes: int = 0,
    person: str = "alice",
) -> Claim:
    return Claim(
        id=id,
        changeset_id="c2",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.PERSON,
        entity_id=person,
        field_path=field,
        kind=kind,
        value=value,
    )


@pytest.mark.unit
def test_a_scalar_with_nothing_to_say_is_none():
    assert scalar_value(ALICE, "image", Facts()) is None


@pytest.mark.unit
def test_a_list_with_nothing_to_say_is_empty_not_none():
    """A person with no emails has none, rather than an unknown number of them."""
    assert list_value(ALICE, "emails", Facts()) == ()


@pytest.mark.unit
def test_a_scalar_takes_the_latest_record():
    facts = Facts(
        records=(
            record("r1", minutes=1, name="A. Ng"),
            record("r2", minutes=2, name="Alice Ng"),
        )
    )

    assert scalar_value(ALICE, "name", facts) == "Alice Ng"


@pytest.mark.unit
def test_a_scalar_skips_another_line_of_the_same_read_that_says_nothing():
    """One read, two lines about her: the one that carries a photo answers for the read."""
    facts = Facts(
        records=(
            record("r1", minutes=1, image="alice.jpg"),
            record("r2", minutes=2, image=None),
        )
    )

    assert scalar_value(ALICE, "image", facts) == "alice.jpg"


@pytest.mark.unit
def test_a_later_read_that_drops_the_photo_clears_it():
    """One rule for every field: the current read is the answer. A page that stopped printing
    a photo has stopped printing it, exactly as it would have stopped printing a phone."""
    facts = Facts(
        records=(
            record("r1", changeset_id="c1", minutes=1, image="alice.jpg"),
            record("r2", changeset_id="c2", minutes=2, image=None),
        )
    )

    assert scalar_value(ALICE, "image", facts) is None


@pytest.mark.unit
def test_an_older_read_of_another_organization_still_answers():
    """"Current" is per organization: the council reading again says nothing about what the
    school board's page printed."""
    facts = Facts(
        records=(
            record("r1", changeset_id="c1", minutes=1, image="alice.jpg", organization_id="school"),
            record("r2", changeset_id="c2", minutes=2, image=None),
        )
    )

    assert scalar_value(ALICE, "image", facts) == "alice.jpg"


@pytest.mark.unit
def test_a_claim_beats_every_record_however_new():
    """R7, and scenario 2: a scrape must not overwrite what a person typed."""
    facts = Facts(
        records=(record("r1", minutes=5, name="Wrong Name"),),
        claims=(claim("k1", "name", "Alice Ng", minutes=1),),
    )

    assert scalar_value(ALICE, "name", facts) == "Alice Ng"


@pytest.mark.unit
def test_the_newest_claim_wins():
    """Scenario 3: Carol says one thing, Dave says another later."""
    facts = Facts(
        claims=(
            claim("k1", "name", "Carol's answer", minutes=1),
            claim("k2", "name", "Dave's answer", minutes=2),
        )
    )

    assert scalar_value(ALICE, "name", facts) == "Dave's answer"


@pytest.mark.unit
def test_a_claim_on_either_half_of_a_merge_counts():
    """`members` is the whole cluster, so where the claim was filed does not matter."""
    facts = Facts(claims=(claim("k1", "name", "Alice Ng", person="alice2"),))

    assert scalar_value({"alice", "alice2"}, "name", facts) == "Alice Ng"


@pytest.mark.unit
def test_a_claim_about_another_person_is_ignored():
    facts = Facts(
        records=(record("r1", name="Alice Ng"),),
        claims=(claim("k1", "name", "Bob's name", person="bob"),),
    )

    assert scalar_value(ALICE, "name", facts) == "Alice Ng"


@pytest.mark.unit
def test_a_rejected_scalar_leaves_nothing():
    """Rejecting the only value the page has is how a person says it is wrong without
    supplying a replacement."""
    facts = Facts(
        records=(record("r1", image="wrong.jpg"),),
        claims=(claim("k1", "image", "wrong.jpg", kind=ClaimKind.REJECT),),
    )

    assert scalar_value(ALICE, "image", facts) is None


@pytest.mark.unit
def test_a_list_unions_every_record():
    facts = Facts(
        records=(
            record("r1", minutes=1, phone="(206) 555-1111"),
            record("r2", minutes=2, phone="(206) 555-2222"),
        )
    )

    assert list_value(ALICE, "phones", facts) == ("(206) 555-1111", "(206) 555-2222")


@pytest.mark.unit
def test_a_list_says_each_value_once():
    facts = Facts(
        records=(
            record("r1", minutes=1, phone="(206) 555-1111"),
            record("r2", minutes=2, phone="(206) 555-1111"),
        )
    )

    assert list_value(ALICE, "phones", facts) == ("(206) 555-1111",)


@pytest.mark.unit
def test_a_list_adds_accepted_values():
    """Somebody typing a second phone number is an accept on the list field."""
    facts = Facts(
        records=(record("r1", minutes=1, phone="(206) 555-1111"),),
        claims=(claim("k1", "phones", "(206) 555-9999", minutes=2),),
    )

    assert list_value(ALICE, "phones", facts) == ("(206) 555-1111", "(206) 555-9999")


@pytest.mark.unit
def test_a_list_drops_rejected_values():
    """And it stays dropped when the next scrape says it again, which is what makes a reject
    different from withdrawing the record."""
    facts = Facts(
        records=(
            record("r1", minutes=1, phone="(206) 555-1111"),
            record("r2", minutes=2, phone="(206) 555-2222"),
        ),
        claims=(claim("k1", "phones", "(206) 555-1111", kind=ClaimKind.REJECT, minutes=3),),
    )

    assert list_value(ALICE, "phones", facts) == ("(206) 555-2222",)


@pytest.mark.unit
def test_a_reject_beats_an_accept_of_the_same_value():
    """Both are live claims about one value; the value is suppressed."""
    facts = Facts(
        claims=(
            claim("k1", "phones", "(206) 555-1111", minutes=1),
            claim("k2", "phones", "(206) 555-1111", kind=ClaimKind.REJECT, minutes=2),
        )
    )

    assert list_value(ALICE, "phones", facts) == ()


@pytest.mark.unit
def test_rejecting_a_typed_scalar_falls_back_to_the_records():
    """R7 on one value: the reject is the newest thing said about "Smith", so the typed value
    goes and what the page says stands again."""
    facts = Facts(
        records=(record("r1", minutes=1, name="Jones"),),
        claims=(
            claim("k1", "name", "Smith", minutes=2),
            claim("k2", "name", "Smith", kind=ClaimKind.REJECT, minutes=3),
        ),
    )

    assert scalar_value(ALICE, "name", facts) == "Jones"


@pytest.mark.unit
def test_accepting_a_rejected_value_again_brings_it_back():
    """The other half of R7: a reject is not permanent, it is just the last word so far."""
    facts = Facts(
        claims=(
            claim("k1", "phones", "(206) 555-1111", kind=ClaimKind.REJECT, minutes=1),
            claim("k2", "phones", "(206) 555-1111", minutes=2),
        )
    )

    assert list_value(ALICE, "phones", facts) == ("(206) 555-1111",)


@pytest.mark.unit
def test_a_list_value_the_page_stopped_printing_is_gone():
    """Monday's page had two numbers, Tuesday's page one. The dropped number goes with the read
    that last printed it; today's publish overwrote it the same way."""
    facts = Facts(
        records=(
            record("r1", minutes=1, changeset_id="c1", phone="(206) 555-1111"),
            record("r2", minutes=2, changeset_id="c2", phone="(206) 555-2222"),
        )
    )

    assert list_value(ALICE, "phones", facts) == ("(206) 555-2222",)


@pytest.mark.unit
def test_a_list_value_from_another_organizations_page_stays():
    """The school page still lists the number; the council page being read again says nothing
    about it. Today's publish would have dropped it, since the last publish wins."""
    facts = Facts(
        records=(
            record("r1", minutes=1, changeset_id="c1", organization_id="school", phone="(206) 555-1111"),
            record("r2", minutes=2, changeset_id="c2", phone="(206) 555-2222"),
        )
    )

    assert list_value(ALICE, "phones", facts) == ("(206) 555-1111", "(206) 555-2222")


@pytest.mark.unit
def test_a_phone_from_a_page_is_normalised():
    """A page prints a number its own way; the projection holds one spelling, as publish did."""
    facts = Facts(records=(record("r1", phone="909-797-2489"),))

    assert list_value(ALICE, "phones", facts) == ("(909) 797-2489",)


@pytest.mark.unit
def test_a_phone_that_will_not_normalise_is_dropped():
    facts = Facts(records=(record("r1", phone="call the clerk"),))

    assert list_value(ALICE, "phones", facts) == ()


@pytest.mark.unit
def test_an_email_from_a_page_is_lowercased():
    facts = Facts(records=(record("r1", email="Rob.Saka@Seattle.gov"),))

    assert list_value(ALICE, "emails", facts) == ("rob.saka@seattle.gov",)


@pytest.mark.unit
def test_a_reject_matches_the_normalised_value():
    """Rejects are filed against the published value, which is the normalised one."""
    facts = Facts(
        records=(record("r1", phone="909-797-2489"),),
        claims=(claim("k1", "phones", "(909) 797-2489", kind=ClaimKind.REJECT),),
    )

    assert list_value(ALICE, "phones", facts) == ()


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6: the same facts rebuild the same projection, whatever order the loader returns."""
    records = (
        record("r1", minutes=1, phone="(206) 555-1111"),
        record("r2", minutes=2, phone="(206) 555-2222"),
    )
    claims = (
        claim("k1", "name", "First", minutes=1),
        claim("k2", "name", "Second", minutes=2),
    )

    forwards = Facts(records=records, claims=claims)
    backwards = Facts(records=tuple(reversed(records)), claims=tuple(reversed(claims)))

    assert list_value(ALICE, "phones", forwards) == list_value(ALICE, "phones", backwards)
    assert scalar_value(ALICE, "name", forwards) == scalar_value(ALICE, "name", backwards)
