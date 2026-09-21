"""What `current_records` must answer.

The rule that keeps a list field from growing forever: per organization, a person's evidence
is their newest listing there. Not the organization's latest read, which is the membership
rule: a page dropping someone retires them, it does not erase what it last said about them.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.projection.facts import Facts, SourceRecord
from core.projection.field_value import current_records

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
ALICE = {"alice"}
COUNCIL = "council"
SCHOOL = "school"


def record(
    id: str,
    changeset: str,
    organization: str = COUNCIL,
    person: str = "alice",
    minutes: int = 0,
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=organization,
        name="Alice Ng",
        label="mayor",
        source_url=f"https://example.gov/{organization}",
    )


def ids(records):
    return [r.id for r in records]


@pytest.mark.unit
def test_no_records_nothing_current():
    assert current_records(ALICE, Facts()) == []


@pytest.mark.unit
def test_the_only_read_is_current():
    facts = Facts(records=(record("r1", "c1"),))

    assert ids(current_records(ALICE, facts)) == ["r1"]


@pytest.mark.unit
def test_a_read_since_replaced_is_not_current():
    """Monday listed Alice with one phone, Tuesday with another. Monday's record is history."""
    facts = Facts(records=(record("r1", "c1", minutes=1), record("r2", "c2", minutes=2)))

    assert ids(current_records(ALICE, facts)) == ["r2"]


@pytest.mark.unit
def test_a_person_the_latest_read_dropped_keeps_their_last_listing():
    """The page was read again without Alice. Her membership retires on that read, but the
    page stopping to list her has not said her phone number is wrong: the last page that did
    list her is still her evidence, as it is today."""
    facts = Facts(
        records=(
            record("r1", "c1", minutes=1),
            record("r2", "c2", person="bob", minutes=2),
        )
    )

    assert ids(current_records(ALICE, facts)) == ["r1"]


@pytest.mark.unit
def test_each_organization_keeps_its_own_latest_read():
    """Alice on the council page (read Monday) and the school page (read Tuesday). Both are
    current: Tuesday's read of the school says nothing about the council."""
    facts = Facts(
        records=(
            record("r1", "c1", organization=COUNCIL, minutes=1),
            record("r2", "c2", organization=SCHOOL, minutes=2),
        )
    )

    assert ids(current_records(ALICE, facts)) == ["r1", "r2"]


@pytest.mark.unit
def test_several_records_from_the_latest_read_all_count():
    """One scrape can list a person twice in one organization, two pages say."""
    facts = Facts(records=(record("r1", "c1", minutes=1), record("r2", "c1", minutes=2)))

    assert ids(current_records(ALICE, facts)) == ["r1", "r2"]


@pytest.mark.unit
def test_another_persons_records_are_not_mine():
    facts = Facts(records=(record("r1", "c1", person="bob"),))

    assert current_records(ALICE, facts) == []


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6, and oldest first, since `list_value` keeps record order."""
    records = (
        record("r1", "c1", organization=COUNCIL, minutes=1),
        record("r2", "c2", organization=SCHOOL, minutes=2),
        record("r3", "c3", organization=COUNCIL, minutes=3),
    )

    forwards = current_records(ALICE, Facts(records=records))
    backwards = current_records(ALICE, Facts(records=tuple(reversed(records))))

    assert forwards == backwards
    assert ids(forwards) == ["r2", "r3"]
