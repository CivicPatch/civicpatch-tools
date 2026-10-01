"""A deleted post's facts read as the post that took its memberships."""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.membership_ids import membership_id
from shared.utils.taxonomy import build_taxonomy

from core.people_edits import POSTS_FIELD
from core.projection.canonical_ids import SAME_AS
from core.projection.facts import Claim, ClaimKind, EntityType, Facts, PostKey, SourceRecord
from core.projection.memberships import MEMBERSHIP_LABEL_FIELD, MEMBERSHIP_START_DATE_FIELD
from core.projection.post_merges import post_merges, with_post_merges
from core.projection.roster import derive_roster

pytestmark = pytest.mark.unit

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
BASE = "ocd-division/country:us/state:wa/place:seattle"
COUNCIL = "council"
MAYORS_OFFICE = "office-of-the-mayor"
EXECUTIVE = "executive"

TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="mayor", label="Mayor", status=RoleStatus.ACTIVE, aliases=[], priority=10, is_unique=True),
        ]
    )
)
COUNCIL_MAYOR = PostKey(organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE)
OFFICE_MAYOR = PostKey(organization_id=MAYORS_OFFICE, role_id="mayor", division_ocdid=BASE)
EXECUTIVE_MAYOR = PostKey(organization_id=EXECUTIVE, role_id="mayor", division_ocdid=BASE)


def record(id: str, person: str, organization: str = COUNCIL, minutes: int = 0) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=organization,
        name="Katie Wilson",
        label="Mayor",
        source_url="https://seattle.gov/mayor",
    )


def claim(id: str, entity_type: EntityType, entity_id: str, field: str | None, value, **extra) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=extra.pop("minutes", 5)),
        entity_type=entity_type,
        entity_id=entity_id,
        field_path=field,
        kind=extra.pop("kind", ClaimKind.ACCEPT),
        value=value,
        **extra,
    )


def merge(id: str, post: PostKey, into: PostKey) -> Claim:
    """As the loader hands it over: the target's id, and its key resolved from the posts row."""
    return claim(id, EntityType.POST, post.post_id, SAME_AS, into.post_id, post=into)


def posts_of(facts: Facts) -> list[PostKey]:
    roster = derive_roster(facts, JURISDICTION, TAXONOMY)
    return [membership.post for person in roster.people for membership in person.memberships]


def test_without_a_merge_the_facts_are_untouched():
    facts = Facts(records=(record("r1", "katie"),))
    assert with_post_merges(facts, JURISDICTION, TAXONOMY) is facts


def test_the_mayor_read_under_council_is_held_in_the_mayors_office():
    facts = Facts(records=(record("r1", "katie"),), claims=(merge("m1", COUNCIL_MAYOR, OFFICE_MAYOR),))
    assert posts_of(facts) == [OFFICE_MAYOR]


def test_read_under_both_organizations_is_one_membership():
    """The Seattle duplicate: the same page read for both organizations."""
    facts = Facts(
        records=(record("r1", "katie"), record("r2", "katie", organization=MAYORS_OFFICE)),
        claims=(merge("m1", COUNCIL_MAYOR, OFFICE_MAYOR),),
    )
    assert posts_of(facts) == [OFFICE_MAYOR]


def test_withdrawing_the_merge_puts_the_mayor_back_on_council():
    the_merge = merge("m1", COUNCIL_MAYOR, OFFICE_MAYOR)
    withdraw = claim("w1", EntityType.CLAIM, the_merge.id, None, None, kind=ClaimKind.WITHDRAW)
    facts = Facts(records=(record("r1", "katie"),), claims=(the_merge,), withdraws=(withdraw,))
    assert posts_of(facts) == [COUNCIL_MAYOR]


def test_a_membership_label_moves_with_the_membership():
    label = claim(
        "l1", EntityType.MEMBERSHIP, membership_id("katie", COUNCIL_MAYOR.post_id), MEMBERSHIP_LABEL_FIELD, "Acting"
    )
    facts = Facts(records=(record("r1", "katie"),), claims=(merge("m1", COUNCIL_MAYOR, OFFICE_MAYOR), label))

    merged = with_post_merges(facts, JURISDICTION, TAXONOMY)

    [moved] = [c for c in merged.claims if c.id == "l1"]
    assert moved.entity_id == membership_id("katie", OFFICE_MAYOR.post_id)


def test_a_hand_placement_on_the_old_post_names_the_new_one():
    placed = claim(
        "p1", EntityType.PERSON, "katie", POSTS_FIELD, COUNCIL_MAYOR.post_id, post=COUNCIL_MAYOR
    )
    facts = Facts(claims=(merge("m1", COUNCIL_MAYOR, OFFICE_MAYOR), placed))

    merged = with_post_merges(facts, JURISDICTION, TAXONOMY)

    [moved] = [c for c in merged.claims if c.id == "p1"]
    assert (moved.post, moved.value) == (OFFICE_MAYOR, OFFICE_MAYOR.post_id)


def test_a_post_merged_twice_ends_where_the_chain_ends():
    facts = Facts(
        records=(record("r1", "katie"),),
        claims=(merge("m1", COUNCIL_MAYOR, OFFICE_MAYOR), merge("m2", OFFICE_MAYOR, EXECUTIVE_MAYOR)),
    )
    assert post_merges(facts, JURISDICTION, TAXONOMY) == {
        COUNCIL_MAYOR: EXECUTIVE_MAYOR,
        OFFICE_MAYOR: EXECUTIVE_MAYOR,
    }
    assert posts_of(facts) == [EXECUTIVE_MAYOR]


def test_a_target_with_another_role_is_ignored():
    """Records are re-read by organization alone, so only the same office elsewhere can take them."""
    clerk = PostKey(organization_id=MAYORS_OFFICE, role_id="clerk", division_ocdid=BASE)
    facts = Facts(records=(record("r1", "katie"),), claims=(merge("m1", COUNCIL_MAYOR, clerk),))
    assert posts_of(facts) == [COUNCIL_MAYOR]


def test_a_merge_naming_a_post_nothing_derives_is_inert():
    stranger = PostKey(organization_id="planning", role_id="mayor", division_ocdid=BASE)
    facts = Facts(records=(record("r1", "katie"),), claims=(merge("m1", stranger, OFFICE_MAYOR),))
    assert posts_of(facts) == [COUNCIL_MAYOR]


def test_dates_on_both_memberships_combine_and_the_newest_stands():
    """Held in both organizations at once: one membership, and of two start dates the one said
    last wins, as anywhere else in the fold."""
    on_council = claim(
        "d1", EntityType.MEMBERSHIP, membership_id("katie", COUNCIL_MAYOR.post_id),
        MEMBERSHIP_START_DATE_FIELD, "2025-01-01", minutes=6,
    )
    in_office = claim(
        "d2", EntityType.MEMBERSHIP, membership_id("katie", OFFICE_MAYOR.post_id),
        MEMBERSHIP_START_DATE_FIELD, "2026-01-01", minutes=7,
    )
    facts = Facts(
        records=(record("r1", "katie"), record("r2", "katie", organization=MAYORS_OFFICE)),
        claims=(merge("m1", COUNCIL_MAYOR, OFFICE_MAYOR), on_council, in_office),
    )

    [person] = derive_roster(facts, JURISDICTION, TAXONOMY).people
    [membership] = person.memberships
    assert (membership.post, membership.start_date) == (OFFICE_MAYOR, "2026-01-01")
