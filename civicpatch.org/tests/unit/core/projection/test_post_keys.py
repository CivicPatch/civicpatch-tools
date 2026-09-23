"""What `post_keys` must answer: the posts the writer makes sure exist before it inserts
memberships that point at them."""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import PostKey, SourceRecord
from core.projection.posts import post_keys

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
BASE = "ocd-division/country:us/state:tx/place:alpha"
COUNCIL = "council"
SCHOOL = "school"


def _role(id_, label, priority):
    return Role(
        id=id_, label=label, status=RoleStatus.ACTIVE, aliases=[], priority=priority,
        is_unique=False,
    )


ROLES = [
    _role("mayor", "Mayor", 10),
    _role("council-member", "Council Member", 500),
    _role("board-member", "Board Member", 400),
]
TAXONOMY = build_taxonomy(RoleConfig(roles=ROLES))

MAYOR = PostKey(organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE)
COUNCIL_MEMBER = PostKey(organization_id=COUNCIL, role_id="council-member", division_ocdid=BASE)
BOARD_MEMBER = PostKey(organization_id=SCHOOL, role_id="board-member", division_ocdid=BASE)


def record(
    id: str,
    label: str,
    person: str = "alice",
    changeset: str = "c1",
    organization: str = COUNCIL,
    minutes: int = 0,
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=organization,
        name="Alice Ng",
        label=label,
        source_url="https://example.gov/council",
    )


def keys(*records: SourceRecord) -> tuple[PostKey, ...]:
    return post_keys(records, JURISDICTION, TAXONOMY, ROLES)


@pytest.mark.unit
def test_no_records_derive_no_posts():
    assert keys() == ()


@pytest.mark.unit
def test_two_people_on_one_post_is_one_post():
    assert keys(record("r1", "Mayor"), record("r2", "Mayor", person="bob")) == (MAYOR,)


@pytest.mark.unit
def test_the_same_post_scraped_twice_is_one_post():
    assert keys(
        record("r1", "Mayor", changeset="c1"), record("r2", "Mayor", changeset="c2", minutes=1)
    ) == (MAYOR,)


@pytest.mark.unit
def test_each_person_is_parsed_on_their_own():
    """Bob's label must not leak into Alice's parse just because one page listed both."""
    derived = keys(record("r1", "Mayor"), record("r2", "Council Member", person="bob"))

    assert set(derived) == {MAYOR, COUNCIL_MEMBER}


@pytest.mark.unit
def test_each_organization_is_parsed_on_its_own():
    derived = keys(record("r1", "Mayor"), record("r2", "Board Member", organization=SCHOOL))

    assert set(derived) == {MAYOR, BOARD_MEMBER}


@pytest.mark.unit
def test_posts_come_back_sorted_by_post_id():
    """R6: two rebuilds of the same facts insert posts in the same order."""
    derived = keys(
        record("r1", "Board Member", organization=SCHOOL),
        record("r2", "Council Member", person="bob"),
        record("r3", "Mayor", person="carol"),
    )

    assert [key.post_id for key in derived] == sorted(key.post_id for key in derived)
