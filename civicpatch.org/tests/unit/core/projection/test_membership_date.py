"""`membership_date`: a human's date beats the page's, and the latest page to say one wins."""

from datetime import datetime, timedelta, timezone

import pytest

from shared.utils.membership_ids import membership_id

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord
from core.projection.memberships import END_DATE, START_DATE, membership_date

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
POST = "post-mayor"
ALICE = {"alice"}


def record(id: str, minutes: int = 0, **fields) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=f"c-{id}",
        created_at=_T + timedelta(minutes=minutes),
        person_id="alice",
        organization_id="council",
        name="Alice Ng",
        label="Mayor",
        source_url="https://example.gov/council",
        **fields,
    )


def date_claim(
    id: str, field: str, value: str, kind: ClaimKind = ClaimKind.ACCEPT, minutes: int = 0
) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id("alice", POST),
        field_path=field,
        kind=kind,
        value=value,
    )


def date(field: str, records: list[SourceRecord], claims: tuple[Claim, ...] = ()):
    facts = Facts(records=tuple(records), claims=claims)
    return membership_date(ALICE, POST, field, records, facts)


@pytest.mark.unit
def test_no_record_and_no_claim_says_nothing():
    assert date(START_DATE, []) is None


@pytest.mark.unit
def test_the_latest_record_that_gives_a_date_wins():
    records = [
        record("r0", minutes=0, start_date="2020-01-01"),
        record("r1", minutes=10, start_date="2022-01-01"),
        record("r2", minutes=20),
    ]
    assert date(START_DATE, records) == "2022-01-01"


@pytest.mark.unit
def test_an_accept_beats_any_record():
    records = [record("r0", minutes=30, end_date="2030-01-01")]
    claims = (date_claim("a0", END_DATE, "2028-01-01", minutes=0),)
    assert date(END_DATE, records, claims) == "2028-01-01"


@pytest.mark.unit
def test_the_latest_accept_wins():
    claims = (
        date_claim("a0", START_DATE, "2020-01-01", minutes=0),
        date_claim("a1", START_DATE, "2021-01-01", minutes=10),
    )
    assert date(START_DATE, [], claims) == "2021-01-01"


@pytest.mark.unit
def test_a_claim_on_the_other_date_field_is_ignored():
    claims = (date_claim("a0", END_DATE, "2028-01-01"),)
    assert date(START_DATE, [record("r0", start_date="2020-01-01")], claims) == "2020-01-01"
