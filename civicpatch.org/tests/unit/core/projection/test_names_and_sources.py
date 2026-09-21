"""What `other_names` and `source_urls` must answer.

Both are today's `people_derivation` rules moved onto current records: `source_urls` from
`get_source_urls`, `other_names` from the loop that collects every spelling a record used and
drops the published one.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord
from core.projection.field_value import other_names, source_urls

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
ALICE = {"alice"}
COUNCIL_PAGE = "https://example.gov/council"
SCHOOL_PAGE = "https://example.gov/school"


def record(
    id: str,
    name: str = "Alice Ng",
    changeset: str = "c1",
    organization: str = "council",
    page: str = COUNCIL_PAGE,
    minutes: int = 0,
    other: tuple[str, ...] = (),
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id="alice",
        organization_id=organization,
        name=name,
        label="mayor",
        source_url=page,
        other_names=other,
    )


def claim(
    id: str, field: str, value, kind: ClaimKind = ClaimKind.ACCEPT, minutes: int = 0
) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.PERSON,
        entity_id="alice",
        field_path=field,
        kind=kind,
        value=value,
    )


# --- source_urls ---


@pytest.mark.unit
def test_no_records_no_sources():
    assert source_urls(ALICE, Facts()) == ()


@pytest.mark.unit
def test_each_page_once_sorted():
    facts = Facts(
        records=(
            record("r1", page=SCHOOL_PAGE, organization="school", minutes=1),
            record("r2", page=COUNCIL_PAGE, minutes=2),
            record("r3", page=COUNCIL_PAGE, minutes=3),
        )
    )

    assert source_urls(ALICE, facts) == (COUNCIL_PAGE, SCHOOL_PAGE)


@pytest.mark.unit
def test_a_page_that_stopped_listing_them_is_still_their_last_source():
    """Current records are the newest listing per organization: the council page was read
    again without Alice, and it is still the page that last named her."""
    facts = Facts(
        records=(
            record("r1", page=COUNCIL_PAGE, changeset="c1", minutes=1),
            SourceRecord(
                id="r2",
                changeset_id="c2",
                created_at=_T + timedelta(minutes=2),
                person_id="bob",
                organization_id="council",
                name="Bob",
                label="member",
                source_url=COUNCIL_PAGE,
            ),
        )
    )

    assert source_urls(ALICE, facts) == (COUNCIL_PAGE,)


@pytest.mark.unit
def test_a_claim_is_not_a_source():
    """`NOT_ASSERTABLE` today: a human typing a value cites no page."""
    facts = Facts(claims=(claim("k1", "source_urls", "https://typed.example"),))

    assert source_urls(ALICE, facts) == ()


# --- other_names ---


@pytest.mark.unit
def test_no_records_no_other_names():
    assert other_names(ALICE, Facts()) == ()


@pytest.mark.unit
def test_the_published_name_is_not_an_other_name():
    facts = Facts(records=(record("r1", name="Alice Ng"),))

    assert other_names(ALICE, facts) == ()


@pytest.mark.unit
def test_a_second_spelling_is_an_other_name():
    """Two pages, two spellings. The newest is the name; the other is kept as a spelling."""
    facts = Facts(
        records=(
            record("r1", name="A. Ng", minutes=1),
            record("r2", name="Alice Ng", minutes=2),
        )
    )

    assert other_names(ALICE, facts) == ("A. Ng",)


@pytest.mark.unit
def test_a_records_own_other_names_are_included():
    facts = Facts(records=(record("r1", name="Alice Ng", other=("Ali Ng",)),))

    assert other_names(ALICE, facts) == ("Ali Ng",)


@pytest.mark.unit
def test_spellings_that_are_the_same_name_count_once():
    """Case, accents and punctuation set aside: "a ng" and "A. Ng" are one spelling, and
    neither is "Alice Ng" spelled differently."""
    facts = Facts(
        records=(
            record("r1", name="A. Ng", minutes=1),
            record("r2", name="a ng", minutes=2),
            record("r3", name="ALICE NG", minutes=3),
        )
    )

    assert other_names(ALICE, facts) == ("A. Ng",)


@pytest.mark.unit
def test_other_names_come_back_sorted():
    facts = Facts(
        records=(record("r1", name="Alice Ng", other=("Zed", "Ali", "Mo")),)
    )

    assert other_names(ALICE, facts) == ("Ali", "Mo", "Zed")


@pytest.mark.unit
def test_an_accepted_other_name_is_added():
    facts = Facts(
        records=(record("r1", name="Alice Ng"),),
        claims=(claim("k1", "other_names", "Lissy"),),
    )

    assert other_names(ALICE, facts) == ("Lissy",)


@pytest.mark.unit
def test_a_rejected_other_name_is_dropped():
    facts = Facts(
        records=(record("r1", name="Alice Ng", other=("Ali Ng",)),),
        claims=(claim("k1", "other_names", "Ali Ng", kind=ClaimKind.REJECT),),
    )

    assert other_names(ALICE, facts) == ()


@pytest.mark.unit
def test_a_spelling_from_a_page_that_stopped_listing_them_is_gone():
    """Current records only, like every other list."""
    facts = Facts(
        records=(
            record("r1", name="A. Ng", changeset="c1", minutes=1),
            record("r2", name="Alice Ng", changeset="c2", minutes=2),
        )
    )

    assert other_names(ALICE, facts) == ()


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6."""
    records = (
        record("r1", name="A. Ng", minutes=1, other=("Ali",)),
        record("r2", name="Alice Ng", minutes=2),
    )

    forwards = Facts(records=records)
    backwards = Facts(records=tuple(reversed(records)))

    assert other_names(ALICE, forwards) == other_names(ALICE, backwards)
    assert source_urls(ALICE, forwards) == source_urls(ALICE, backwards)
