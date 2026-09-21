"""What `post_of` must answer.

Today's `derived_posts` rule, kept: one person's labels in one organization parse together,
the highest-priority role wins, an unknown label still lands on the organization's unmatched
post.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import UNMATCHED_ROLE_ID, build_taxonomy

from core.projection.facts import SourceRecord
from core.projection.posts import PostKey, post_of

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
BASE = "ocd-division/country:us/state:tx/place:alpha"
COUNCIL = "council"


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
]
TAXONOMY = build_taxonomy(RoleConfig(roles=ROLES))


def record(id: str, label: str, minutes: int = 0) -> SourceRecord:
    """Alice seen under `label` on the council page. `minutes` orders the records."""
    return SourceRecord(
        id=id,
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
        person_id="alice",
        organization_id=COUNCIL,
        name="Alice Ng",
        label=label,
        source_url="https://example.gov/council",
    )


def key(role_id: str, division: str = BASE) -> PostKey:
    return PostKey(organization_id=COUNCIL, role_id=role_id, division_ocdid=division)


@pytest.mark.unit
def test_a_posts_id_is_a_pure_function_of_its_key():
    """The fold must address a post it has just derived, before any row exists. A lookup in
    `posts` cannot serve: R6 truncates that table and rebuilds it from facts."""
    assert key("mayor").post_id == key("mayor").post_id
    assert uuid.UUID(key("mayor").post_id)
    assert key("mayor").post_id != key("council-member").post_id
    assert key("mayor").post_id != key("mayor", division=BASE + "/council_district:3").post_id


@pytest.mark.unit
def test_a_posts_id_never_changes():
    """Every membership claim is addressed by `uuid5(person_id, post_id)`, so changing this
    encoding orphans all of them silently."""
    stable = PostKey(
        organization_id="11111111-1111-1111-1111-111111111111",
        role_id="mayor",
        division_ocdid="ocd-division/country:us/state:tx/place:alpha",
    )

    assert stable.post_id == "6b8b8b58-64cb-5dc2-8418-4354ee907624"


@pytest.mark.unit
def test_a_known_label_maps_to_its_role():
    assert post_of([record("r1", "Mayor")], JURISDICTION, TAXONOMY, ROLES) == key("mayor")


@pytest.mark.unit
def test_an_alias_maps_to_its_role():
    assert post_of([record("r1", "Councilman")], JURISDICTION, TAXONOMY, ROLES) == key(
        "council-member"
    )


@pytest.mark.unit
def test_an_unknown_label_still_lands_on_a_post():
    """The person keeps a membership, under the unmatched role, with the label right there for
    a human to map later. Today's behaviour, kept on purpose."""
    assert post_of([record("r1", "Grand Vizier")], JURISDICTION, TAXONOMY, ROLES) == key(
        UNMATCHED_ROLE_ID
    )


@pytest.mark.unit
def test_several_labels_pick_the_highest_priority_role():
    """One post per organization from evidence: two pages calling Alice two things is one
    membership, under the role that outranks."""
    records = [
        record("r1", "Council Member", minutes=1),
        record("r2", "Mayor", minutes=2),
    ]

    assert post_of(records, JURISDICTION, TAXONOMY, ROLES) == key("mayor")


@pytest.mark.unit
def test_a_district_in_the_label_sets_the_division():
    result = post_of([record("r1", "Council Member District 3")], JURISDICTION, TAXONOMY, ROLES)

    assert result.role_id == "council-member"
    assert result.division_ocdid.endswith("council_district:3")


@pytest.mark.unit
def test_each_changeset_parses_on_its_own():
    """Called once per changeset, never across them. Monday's Mayor and Tuesday's District 5
    are two posts, not a Mayor of District 5; District 2 then District 5 are two posts, not
    the first division forever."""
    monday = post_of([record("r1", "Mayor", minutes=1)], JURISDICTION, TAXONOMY, ROLES)
    tuesday = post_of(
        [record("r2", "Council Member District 5", minutes=2)], JURISDICTION, TAXONOMY, ROLES
    )
    later = post_of(
        [record("r3", "Council Member District 2", minutes=3)], JURISDICTION, TAXONOMY, ROLES
    )

    assert monday == key("mayor")
    assert tuesday.role_id == "council-member"
    assert tuesday.division_ocdid.endswith("council_district:5")
    assert later.division_ocdid.endswith("council_district:2")
    assert len({monday, tuesday, later}) == 3


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_records_arrive():
    """R6, and the first label naming a division decides it, so the order the labels are
    parsed in has to be the records' own order rather than the loader's."""
    records = [
        record("r1", "Council Member District 3", minutes=1),
        record("r2", "Council Member District 5", minutes=2),
    ]

    forwards = post_of(records, JURISDICTION, TAXONOMY, ROLES)
    backwards = post_of(list(reversed(records)), JURISDICTION, TAXONOMY, ROLES)

    assert forwards == backwards
    assert forwards.division_ocdid.endswith("council_district:3")
