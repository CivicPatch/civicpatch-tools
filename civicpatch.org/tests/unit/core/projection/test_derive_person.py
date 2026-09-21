"""What `derive_person` must answer.

The assembly: fields from `field_value`, posts from the records union the `exists` claims,
each post's state from `membership_state`. The cases here are the seams between those, not
the rules inside them, which their own tests cover.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.membership_ids import membership_id
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, SourceRecord
from core.projection.memberships import LISTED_AFTER_CLOSE
from core.projection.people import derive_person
from core.projection.posts import PostKey

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
BASE = "ocd-division/country:us/state:tx/place:alpha"
COUNCIL = "council"
ALICE = {"alice"}


def _role(id_, label, priority):
    return Role(
        id=id_, label=label, status=RoleStatus.ACTIVE, aliases=[], priority=priority,
        is_unique=False,
    )


ROLES = [_role("mayor", "Mayor", 10), _role("council-member", "Council Member", 500)]
TAXONOMY = build_taxonomy(RoleConfig(roles=ROLES))

MAYOR = PostKey(
    organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE
).post_id
COUNCIL_MEMBER = PostKey(
    organization_id=COUNCIL, role_id="council-member", division_ocdid=BASE
).post_id


def record(
    id: str,
    label: str = "Mayor",
    changeset: str = "c1",
    person: str = "alice",
    minutes: int = 0,
    **fields,
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=COUNCIL,
        name=fields.pop("name", "Alice Ng"),
        label=label,
        source_url="https://example.gov/council",
        **fields,
    )


def person_claim(
    id: str, field: str, value, kind: ClaimKind = ClaimKind.ACCEPT, person: str = "alice",
    minutes: int = 0,
) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.PERSON,
        entity_id=person,
        field_path=field,
        kind=kind,
        value=value,
    )


def membership_claim(
    id: str, post: str, field: str, value, kind: ClaimKind = ClaimKind.ACCEPT,
    person: str = "alice", minutes: int = 0,
) -> Claim:
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id(person, post),
        field_path=field,
        kind=kind,
        value=value,
    )


def derive(members, facts, person_id="alice"):
    return derive_person(person_id, members, facts, JURISDICTION, TAXONOMY, ROLES)


@pytest.mark.unit
def test_a_person_with_no_facts_at_all():
    """Reachable: every record naming them was withdrawn. They publish as an empty row rather
    than vanishing, and `derive_roster` decides whether to list them."""
    person = derive(ALICE, Facts())

    assert person.id == "alice"
    assert person.name is None
    assert person.memberships == ()
    assert person.edited is False


@pytest.mark.unit
def test_fields_come_from_field_value():
    facts = Facts(records=(record("r1", name="Alice Ng", phone="555-1111", image="a.jpg"),))

    person = derive(ALICE, facts)

    assert person.name == "Alice Ng"
    assert person.phones == ("555-1111",)
    assert person.image == "a.jpg"
    assert person.emails == ()


@pytest.mark.unit
def test_a_record_gives_a_membership():
    person = derive(ALICE, Facts(records=(record("r1", "Mayor"),)))

    assert [m.post_id for m in person.memberships] == [MAYOR]


@pytest.mark.unit
def test_a_membership_the_latest_read_dropped_is_gone():
    """Alice was mayor, the page was read again without her, so the membership closes. The
    person still projects."""
    facts = Facts(
        records=(
            record("r1", "Mayor", changeset="c1", minutes=1),
            record("r2", "Mayor", changeset="c2", person="bob", minutes=2),
        )
    )

    person = derive(ALICE, facts)

    assert person.memberships == ()
    assert person.name == "Alice Ng"


@pytest.mark.unit
def test_an_exists_claim_gives_a_membership_with_no_record():
    """A hand-assignment. `records_by_post` finds nothing, so the post can only come from the
    claim locating itself by its own hash."""
    facts = Facts(claims=(membership_claim("k1", MAYOR, "exists", MAYOR),))

    person = derive(ALICE, facts)

    assert [m.post_id for m in person.memberships] == [MAYOR]
    assert person.edited is True


@pytest.mark.unit
def test_posts_from_records_and_claims_union():
    facts = Facts(
        records=(record("r1", "Mayor"),),
        claims=(membership_claim("k1", COUNCIL_MEMBER, "exists", COUNCIL_MEMBER),),
    )

    person = derive(ALICE, facts)

    assert sorted(m.post_id for m in person.memberships) == sorted([MAYOR, COUNCIL_MEMBER])


@pytest.mark.unit
def test_a_label_claim_overrides_the_display_label():
    facts = Facts(
        records=(record("r1", "Mayor"),),
        claims=(membership_claim("k1", MAYOR, "label", "Mayor (interim)"),),
    )

    person = derive(ALICE, facts)

    assert person.memberships[0].label == "Mayor (interim)"


@pytest.mark.unit
def test_a_membership_with_no_label_claim_has_none():
    person = derive(ALICE, Facts(records=(record("r1", "Mayor"),)))

    assert person.memberships[0].label is None


@pytest.mark.unit
def test_an_issue_from_membership_state_is_carried_up():
    facts = Facts(
        records=(
            record("r1", "Mayor", changeset="c1", minutes=1),
            record("r2", "Mayor", changeset="c2", minutes=3),
        ),
        claims=(membership_claim("k1", MAYOR, "closed", True, minutes=2),),
    )

    person = derive(ALICE, facts)

    assert person.memberships == ()
    assert person.issues == (
        type(person.issues[0])(post_id=MAYOR, issue=LISTED_AFTER_CLOSE),
    )


@pytest.mark.unit
def test_a_person_claim_marks_them_edited():
    facts = Facts(
        records=(record("r1", "Mayor"),),
        claims=(person_claim("k1", "name", "Alice N."),),
    )

    assert derive(ALICE, facts).edited is True


@pytest.mark.unit
def test_untouched_records_are_not_edited():
    assert derive(ALICE, Facts(records=(record("r1", "Mayor"),))).edited is False


@pytest.mark.unit
def test_the_cluster_publishes_under_the_id_it_is_known_by():
    """`members` is the whole cluster; the row goes out under the canonical id, and facts on
    either half count."""
    facts = Facts(
        records=(record("r1", "Mayor", person="alice2"),),
        claims=(person_claim("k1", "name", "Alice Ng", person="alice"),),
    )

    person = derive({"alice", "alice2"}, facts, person_id="alice2")

    assert person.id == "alice2"
    assert person.name == "Alice Ng"
    assert [m.post_id for m in person.memberships] == [MAYOR]


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6, and the one that pins the post ordering: two memberships must come back in the same
    order however the loader handed the records over."""
    records = (
        record("r1", "Mayor", changeset="c1", minutes=1),
        record("r2", "Council Member", changeset="c2", minutes=2),
    )
    claims = (membership_claim("k1", COUNCIL_MEMBER, "exists", COUNCIL_MEMBER, minutes=3),)

    forwards = derive(ALICE, Facts(records=records, claims=claims))
    backwards = derive(
        ALICE, Facts(records=tuple(reversed(records)), claims=claims)
    )

    assert forwards == backwards
