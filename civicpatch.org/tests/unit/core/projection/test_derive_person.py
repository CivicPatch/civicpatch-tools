"""What `derive_person` must answer.

The assembly: fields from `field_value`, posts from the records union the accepted posts,
each post's state from `membership_state`, then one per organization. The cases here are the
seams between those, not the rules inside them, which their own tests cover.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.membership_ids import membership_id
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import Claim, ClaimKind, EntityType, Facts, PostKey, SourceRecord
from core.projection.people import derive_person

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

MAYOR_KEY = PostKey(organization_id=COUNCIL, role_id="mayor", division_ocdid=BASE)
MAYOR = MAYOR_KEY.post_id
COUNCIL_MEMBER_KEY = PostKey(
    organization_id=COUNCIL, role_id="council-member", division_ocdid=BASE
)
COUNCIL_MEMBER = COUNCIL_MEMBER_KEY.post_id
SCHOOL = "school"
BOARD_MEMBER_KEY = PostKey(
    organization_id=SCHOOL, role_id="council-member", division_ocdid=BASE
)


def record(
    id: str,
    label: str = "Mayor",
    changeset: str = "c1",
    person: str = "alice",
    minutes: int = 0,
    organization: str = COUNCIL,
    **fields,
) -> SourceRecord:
    return SourceRecord(
        id=id,
        changeset_id=changeset,
        created_at=_T + timedelta(minutes=minutes),
        person_id=person,
        organization_id=organization,
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


def holds(
    id: str, post: PostKey, kind: ClaimKind = ClaimKind.ACCEPT,
    person: str = "alice", minutes: int = 0,
) -> Claim:
    """Somebody said this person holds this post. The loader resolves the key; the stored
    value is the post's id."""
    claim = person_claim(
        id, "posts", post.post_id, kind=kind, person=person, minutes=minutes
    )
    return claim.model_copy(update={"post": post})


def membership_claim(
    id: str, post: PostKey, field: str, value, kind: ClaimKind = ClaimKind.ACCEPT,
    person: str = "alice", minutes: int = 0,
) -> Claim:
    """What the membership is called, or when it ran — keyed by the membership's own id."""
    return Claim(
        id=id,
        changeset_id="c9",
        created_at=_T + timedelta(minutes=minutes),
        entity_type=EntityType.MEMBERSHIP,
        entity_id=membership_id(person, post.post_id),
        field_path=field,
        kind=kind,
        value=value,
    )


def derive(members, facts, person_id="alice"):
    return derive_person(person_id, members, facts, JURISDICTION, TAXONOMY)


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
    facts = Facts(records=(record("r1", name="Alice Ng", phone="(206) 555-1111", image="a.jpg"),))

    person = derive(ALICE, facts)

    assert person.name == "Alice Ng"
    assert person.phones == ("(206) 555-1111",)
    assert person.image == "a.jpg"
    assert person.emails == ()


@pytest.mark.unit
def test_a_record_gives_a_membership():
    person = derive(ALICE, Facts(records=(record("r1", "Mayor"),)))

    assert [m.post.post_id for m in person.memberships] == [MAYOR]


@pytest.mark.unit
def test_a_membership_carries_what_its_records_said():
    facts = Facts(
        records=(
            record("r1", "Mayor", changeset="c1", minutes=1, start_date="2024-01-01"),
            record("r2", "Mayor and Council Member", changeset="c2", minutes=2),
        )
    )

    [membership] = derive(ALICE, facts).memberships

    assert membership.opened_at == _T + timedelta(minutes=1)
    assert membership.start_date == "2024-01-01"
    assert membership.extra_roles == ("council-member",)
    assert [source.note for source in membership.sources] == [
        "Mayor",
        "Mayor and Council Member",
    ]


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
def test_an_accepted_post_gives_a_membership_with_no_record():
    """A hand-assignment. `records_by_post` finds nothing, so the post can only come from the
    claim, which names it."""
    facts = Facts(claims=(holds("k1", MAYOR_KEY),))

    person = derive(ALICE, facts)

    assert [m.post.post_id for m in person.memberships] == [MAYOR]
    assert person.edited is True


@pytest.mark.unit
def test_posts_from_records_and_claims_union():
    """Two organizations: the page puts her on the council, a human on the school board."""
    facts = Facts(
        records=(record("r1", "Mayor"),),
        claims=(holds("k1", BOARD_MEMBER_KEY),),
    )

    person = derive(ALICE, facts)

    assert sorted(m.post.post_id for m in person.memberships) == sorted(
        [MAYOR, BOARD_MEMBER_KEY.post_id]
    )


@pytest.mark.unit
def test_a_label_claim_overrides_the_display_label():
    facts = Facts(
        records=(record("r1", "Mayor"),),
        claims=(membership_claim("k1", MAYOR_KEY, "label", "Mayor (interim)"),),
    )

    person = derive(ALICE, facts)

    assert person.memberships[0].label == "Mayor (interim)"


@pytest.mark.unit
def test_a_membership_with_no_label_claim_has_none():
    person = derive(ALICE, Facts(records=(record("r1", "Mayor"),)))

    assert person.memberships[0].label is None


@pytest.mark.unit
def test_a_move_within_an_organization_keeps_only_the_new_post():
    """A move is an accept on the new post. The page still says mayor, but nothing has been
    read since, so the accept is the most recent thing said and it wins.

    The records stay where they parsed: the term reads "left the mayor's post, holds this
    one", which is what was observed.
    """
    facts = Facts(
        records=(record("r1", "Mayor", minutes=1),),
        claims=(holds("k1", COUNCIL_MEMBER_KEY, minutes=2),),
    )

    person = derive(ALICE, facts)

    assert [m.post.post_id for m in person.memberships] == [COUNCIL_MEMBER]
    assert person.memberships[0].opened_at == _T + timedelta(minutes=2)
    assert person.edited is True


@pytest.mark.unit
def test_a_read_after_the_move_wins_it_back():
    """The page wins at the next read: the council was read again and still says mayor, which
    is now the most recent thing said about where she sits."""
    facts = Facts(
        records=(record("r1", "Mayor", changeset="c1", minutes=1), record("r2", "Mayor", changeset="c2", minutes=3)),
        claims=(holds("k1", COUNCIL_MEMBER_KEY, minutes=2),),
    )

    [membership] = derive(ALICE, facts).memberships

    assert membership.post.post_id == MAYOR
    assert membership.opened_at == _T + timedelta(minutes=1)


@pytest.mark.unit
def test_a_move_leaves_another_organizations_membership_alone():
    """One per organization, not one in total: the collapse groups before it chooses."""
    facts = Facts(
        records=(
            record("r1", "Mayor", changeset="c1", minutes=1),
            record("r2", "Council Member", changeset="c1", organization=SCHOOL, minutes=1),
        ),
        claims=(holds("k1", COUNCIL_MEMBER_KEY, minutes=2),),
    )

    person = derive(ALICE, facts)

    assert sorted(m.post.post_id for m in person.memberships) == sorted(
        [COUNCIL_MEMBER, BOARD_MEMBER_KEY.post_id]
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
    assert [m.post.post_id for m in person.memberships] == [MAYOR]


@pytest.mark.unit
def test_the_answer_does_not_depend_on_the_order_the_facts_arrive():
    """R6, and the one that pins the post ordering: two memberships must come back in the same
    order however the loader handed the records over."""
    records = (
        record("r1", "Mayor", changeset="c1", minutes=1),
        record("r2", "Council Member", changeset="c2", minutes=2),
    )
    claims = (holds("k1", COUNCIL_MEMBER_KEY, minutes=3),)

    forwards = derive(ALICE, Facts(records=records, claims=claims))
    backwards = derive(
        ALICE, Facts(records=tuple(reversed(records)), claims=claims)
    )

    assert forwards == backwards
