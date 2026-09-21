"""What `records_by_post` must answer.

The grouping `post_of` depends on: per changeset and organization when parsing, then collapsed
by post. Getting the first half wrong invents posts nobody held; getting the second wrong
splits one membership into one per scrape.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import SourceRecord
from core.projection.posts import PostKey, records_by_post

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
BASE = "ocd-division/country:us/state:tx/place:alpha"
COUNCIL = "council"
SCHOOL = "school"


def _role(id_, label, aliases, priority):
    return Role(
        id=id_,
        label=label,
        status=RoleStatus.ACTIVE,
        aliases=aliases,
        priority=priority,
        is_unique=False,
    )


ROLES = [
    _role("mayor", "Mayor", [], 10),
    _role("council-member", "Council Member", ["Councilman"], 500),
    _role("board-member", "Board Member", [], 400),
]
TAXONOMY = build_taxonomy(RoleConfig(roles=ROLES))


def record(
    id: str,
    label: str,
    changeset: str = "c1",
    organization: str = COUNCIL,
    minutes: int = 0,
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id="alice",
        organization_id=organization,
        name="Alice Ng",
        label=label,
        source_url="https://example.gov/council",
    )


def grouped(records):
    return records_by_post(records, JURISDICTION, TAXONOMY, ROLES)


def post_id(role_id: str, organization: str = COUNCIL, division: str = BASE) -> str:
    return PostKey(
        organization_id=organization, role_id=role_id, division_ocdid=division
    ).post_id


@pytest.mark.unit
def test_no_records_no_posts():
    assert grouped([]) == {}


@pytest.mark.unit
def test_one_record_one_post():
    result = grouped([record("r1", "Mayor")])

    assert list(result) == [post_id("mayor")]
    assert [r.id for r in result[post_id("mayor")]] == ["r1"]


@pytest.mark.unit
def test_two_labels_in_one_scrape_parse_together():
    """One organization, one changeset: today's rule, the highest-priority role wins and it is
    one membership rather than two."""
    result = grouped(
        [
            record("r1", "Council Member", minutes=1),
            record("r2", "Mayor", minutes=2),
        ]
    )

    assert list(result) == [post_id("mayor")]
    assert len(result[post_id("mayor")]) == 2


@pytest.mark.unit
def test_two_changesets_parse_apart():
    """Monday's Mayor and Tuesday's District 5 are two posts. Parsed together they would give
    a Mayor of District 5, which nobody held."""
    result = grouped(
        [
            record("r1", "Mayor", changeset="c1", minutes=1),
            record("r2", "Council Member District 5", changeset="c2", minutes=2),
        ]
    )

    district_5 = post_id("council-member", division=BASE + "/council_district:5")

    assert set(result) == {post_id("mayor"), district_5}


@pytest.mark.unit
def test_two_organizations_in_one_changeset_parse_apart():
    """A multi-organization scrape. Alice on the council and on the school board holds two
    posts, and neither label may leak into the other."""
    result = grouped(
        [
            record("r1", "Mayor", organization=COUNCIL, minutes=1),
            record("r2", "Board Member", organization=SCHOOL, minutes=2),
        ]
    )

    assert set(result) == {
        post_id("mayor"),
        post_id("board-member", organization=SCHOOL),
    }


@pytest.mark.unit
def test_the_same_post_across_scrapes_is_one_entry():
    """Twenty scrapes of an unchanged page are one membership with twenty records behind it,
    not twenty memberships."""
    result = grouped(
        [
            record("r1", "Mayor", changeset="c1", minutes=1),
            record("r2", "Mayor", changeset="c2", minutes=2),
            record("r3", "Mayor", changeset="c3", minutes=3),
        ]
    )

    assert list(result) == [post_id("mayor")]
    assert [r.id for r in result[post_id("mayor")]] == ["r1", "r2", "r3"]


@pytest.mark.unit
def test_a_move_between_posts_keeps_both_with_their_own_records():
    """`membership_state` decides which is still live; this only has to hand each post the
    records that put the person in it."""
    result = grouped(
        [
            record("r1", "Council Member District 2", changeset="c1", minutes=1),
            record("r2", "Council Member District 5", changeset="c2", minutes=2),
        ]
    )

    district_2 = post_id("council-member", division=BASE + "/council_district:2")
    district_5 = post_id("council-member", division=BASE + "/council_district:5")

    assert [r.id for r in result[district_2]] == ["r1"]
    assert [r.id for r in result[district_5]] == ["r2"]


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_records_arrive():
    """R6. The records inside each bucket are oldest first whatever order they came in."""
    records = [
        record("r1", "Mayor", changeset="c1", minutes=1),
        record("r2", "Mayor", changeset="c2", minutes=2),
        record("r3", "Council Member District 5", changeset="c3", minutes=3),
    ]

    forwards = grouped(records)
    backwards = grouped(list(reversed(records)))

    assert forwards == backwards
    assert [r.id for r in forwards[post_id("mayor")]] == ["r1", "r2"]
