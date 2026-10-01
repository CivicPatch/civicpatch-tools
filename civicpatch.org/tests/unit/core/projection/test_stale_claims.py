"""A claim on a field the page owns holds until every page naming the person is read again."""

from datetime import datetime, timedelta, timezone

import pytest

from core.people_edits import POSTS_FIELD
from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord
from core.projection.field_value import NAME
from core.projection.stale_claims import without_stale_claims

pytestmark = pytest.mark.unit

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
PERSON = "p1"


def record(id: str, organization: str, minutes: int) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=f"scrape-{organization}-{minutes}",
        created_at=_T + timedelta(minutes=minutes),
        person_id=PERSON,
        organization_id=organization,
        name="Katie Wilson",
        label="Mayor",
        source_url=f"https://example.gov/{organization}",
    )


def claim(entity_type: EntityType, field: str, minutes: int) -> Claim:
    return Claim(
        id=f"{field}-{minutes}",
        changeset_id="edit",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=entity_type,
        entity_id=PERSON,
        field_path=field,
        kind=ClaimKind.ACCEPT,
        value="x",
    )


def surviving(records: list[SourceRecord], claims: list[Claim]) -> list[Claim]:
    facts = Facts(records=tuple(records), claims=tuple(claims))
    return list(without_stale_claims({PERSON}, facts).claims)


def test_a_temporary_claim_goes_stale_once_every_page_is_read_again():
    posts = claim(EntityType.PERSON, POSTS_FIELD, 5)
    assert surviving([record("r1", "council", 0), record("r2", "council", 10)], [posts]) == []


def test_a_temporary_claim_holds_until_the_page_is_read_again():
    posts = claim(EntityType.PERSON, POSTS_FIELD, 5)
    assert surviving([record("r1", "council", 0)], [posts]) == [posts]


def test_a_temporary_claim_holds_while_one_page_is_still_older():
    posts = claim(EntityType.PERSON, POSTS_FIELD, 5)
    records = [record("r1", "council", 10), record("r2", "mayors-office", 0)]
    assert surviving(records, [posts]) == [posts]


def test_a_permanent_claim_holds_after_the_page_is_read_again():
    name = claim(EntityType.PERSON, NAME, 5)
    assert surviving([record("r1", "council", 10)], [name]) == [name]


def test_a_person_with_no_records_makes_nothing_stale():
    posts = claim(EntityType.PERSON, POSTS_FIELD, 5)
    assert surviving([], [posts]) == [posts]

