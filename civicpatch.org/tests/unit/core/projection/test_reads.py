"""What `reads_of` must answer.

The retirement rule in `membership_state` rests entirely on this: a person is retired because
the latest read of their organization did not list them. So what counts as a read, and which
read is latest, decides who is on the roster.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Facts, SourcePage, SourceRecord
from core.projection.reads import reads_of

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
COUNCIL = "council"


def page(id: str, changeset: str, *organizations: str, minutes: int = 0) -> SourcePage:
    """A changeset fetched these organizations' pages. `minutes` orders the reads."""
    return SourcePage(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        organization_ids=organizations,
    )


def record(
    id: str, changeset: str, organization: str = COUNCIL, minutes: int = 0
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id="alice",
        organization_id=organization,
        name="Alice Ng",
        label="mayor",
        source_url="https://example.gov/council",
    )


@pytest.mark.unit
def test_nothing_read_nothing():
    assert reads_of(COUNCIL, Facts()) == ()


@pytest.mark.unit
def test_a_page_row_is_a_read():
    facts = Facts(reads=(page("p1", "c1", COUNCIL),))

    assert [r.changeset_id for r in reads_of(COUNCIL, facts)] == ["c1"]


@pytest.mark.unit
def test_a_page_row_for_another_organization_is_not():
    facts = Facts(reads=(page("p1", "c1", "school_board"),))

    assert reads_of(COUNCIL, facts) == ()


@pytest.mark.unit
def test_a_page_row_counts_for_every_organization_it_names():
    """One changeset can read several pages, which is what multi-organization scrapes do."""
    facts = Facts(reads=(page("p1", "c1", COUNCIL, "school_board"),))

    assert [r.changeset_id for r in reads_of(COUNCIL, facts)] == ["c1"]
    assert [r.changeset_id for r in reads_of("school_board", facts)] == ["c1"]


@pytest.mark.unit
def test_a_record_is_a_read_on_its_own():
    """Today's rule, and the only one available for every changeset filed before
    `source_pages` existed: naming an organization means we looked at it."""
    facts = Facts(records=(record("r1", "c1"),))

    assert [r.changeset_id for r in reads_of(COUNCIL, facts)] == ["c1"]


@pytest.mark.unit
def test_a_changeset_reads_an_organization_once_however_many_records():
    facts = Facts(
        records=(
            record("r1", "c1", minutes=1),
            record("r2", "c1", minutes=2),
            record("r3", "c1", minutes=3),
        )
    )

    assert len(reads_of(COUNCIL, facts)) == 1


@pytest.mark.unit
def test_a_page_row_and_its_records_are_one_read_timed_by_the_row():
    """The row is when we looked; the records are only what we found."""
    facts = Facts(
        reads=(page("p1", "c1", COUNCIL, minutes=1),),
        records=(record("r1", "c1", minutes=5),),
    )

    reads = reads_of(COUNCIL, facts)

    assert len(reads) == 1
    assert reads[0].created_at == _T + timedelta(minutes=1)


@pytest.mark.unit
def test_reads_come_back_oldest_first():
    """`membership_state` takes the last one, so this order is the whole contract."""
    facts = Facts(
        reads=(page("p1", "c2", COUNCIL, minutes=2),),
        records=(record("r1", "c1", minutes=1), record("r2", "c3", minutes=3)),
    )

    assert [r.changeset_id for r in reads_of(COUNCIL, facts)] == ["c1", "c2", "c3"]


@pytest.mark.unit
def test_a_withdrawn_scrape_is_not_a_read():
    """`live_facts` has already dropped the withdrawn record, so the read it implied goes with
    it. Computing this from raw facts instead would leave the read standing and retire people
    on the strength of a scrape that no longer exists."""
    rolled_back = Facts(records=(record("r1", "c1", minutes=1),))
    facts = Facts()

    assert len(reads_of(COUNCIL, rolled_back)) == 1
    assert reads_of(COUNCIL, facts) == ()


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6: the same facts rebuild the same projection, whatever order the loader returns."""
    reads = (page("p1", "c2", COUNCIL, minutes=2), page("p2", "c3", COUNCIL, minutes=3))
    records = (record("r1", "c1", minutes=1), record("r2", "c4", minutes=4))

    forwards = Facts(reads=reads, records=records)
    backwards = Facts(reads=tuple(reversed(reads)), records=tuple(reversed(records)))

    assert reads_of(COUNCIL, forwards) == reads_of(COUNCIL, backwards)
