from datetime import datetime, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

from core.display_rows import display_rows
from core.projection.facts import PostKey
from core.projection.membership_details import MembershipSource
from core.projection.people import Membership, Person
from core.projection.roster import Roster

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_JURISDICTION = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"
_BASE = "ocd-division/country:us/state:tx/place:alpha"
_MAYOR = PostKey(organization_id="org-1", role_id="mayor", division_ocdid=_BASE)

TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(
                id="mayor",
                label="Mayor",
                status=RoleStatus.ACTIVE,
                aliases=[],
                priority=10,
                is_unique=False,
            )
        ]
    )
)


def _membership(**overrides) -> Membership:
    return Membership(
        post=_MAYOR,
        opened_at=_T,
        sources=(MembershipSource(note="Mayor", url="https://example.gov/council"),),
        **overrides,
    )


@pytest.mark.unit
def test_a_person_row_carries_the_columns_the_card_reads():
    person = Person(
        id="p1",
        name="Ann Lee",
        phones=("555-0100",),
        memberships=(_membership(label="Interim", start_date="2020-01-01"),),
    )

    [row] = display_rows(Roster(people=(person,)), _JURISDICTION, TAXONOMY)

    assert row["id"] == "p1"
    assert row["name"] == "Ann Lee"
    assert row["phones"] == ["555-0100"]
    assert row["jurisdiction_ocdid"] == _JURISDICTION
    assert row["start_date"] == "2020-01-01"
    assert row["division_ocdid"] == _BASE
    assert row["labels"] == ["Mayor"]
    assert row["sightings"] == [
        {
            "label": "Mayor",
            "source_url": "https://example.gov/council",
            "organization_id": "org-1",
        }
    ]


@pytest.mark.unit
def test_a_membership_row_carries_its_post_and_role_labels():
    person = Person(id="p1", name="Ann Lee", memberships=(_membership(label="Interim"),))

    [row] = display_rows(Roster(people=(person,)), _JURISDICTION, TAXONOMY)
    [membership] = row["memberships"]

    assert membership["post_id"] == _MAYOR.post_id
    assert membership["organization_id"] == "org-1"
    assert membership["role_id"] == "mayor"
    assert membership["role_label"] == "Mayor"
    assert membership["post_label"] == "Mayor"
    assert membership["label"] == "Interim"
    assert membership["source_labels"] == ["Mayor"]
    assert membership["source_urls"] == ["https://example.gov/council"]


@pytest.mark.unit
def test_a_person_with_no_membership_has_no_tenure_fields():
    person = Person(id="p1", name="Ann Lee")

    [row] = display_rows(Roster(people=(person,)), _JURISDICTION, TAXONOMY)

    assert row["memberships"] == []
    assert row["start_date"] is None
    assert row["division_ocdid"] is None
    assert row["sightings"] == []


@pytest.mark.unit
def test_memberships_come_out_in_the_order_the_query_used_to_return_them():
    """`PERSON_MEMBERSHIPS` ordered by role, then division, then post id. The fold orders by
    post id alone, a uuid5 hash, and the card renders these in order."""
    council = PostKey(
        organization_id="org-1",
        role_id="council-member",
        division_ocdid=f"{_BASE}/council_district:2",
    )
    person = Person(
        id="p1",
        name="Ann Lee",
        memberships=(
            _membership(),
            Membership(
                post=council,
                opened_at=_T,
                sources=(MembershipSource(note="Council Member", url=None),),
            ),
        ),
    )

    rows = display_rows(Roster(people=(person,)), _JURISDICTION, TAXONOMY)

    assert [membership["role_id"] for membership in rows[0]["memberships"]] == [
        "council-member",
        "mayor",
    ]


@pytest.mark.unit
def test_people_come_out_in_the_order_the_card_reads_them():
    """By name, as `get_roster` returned them. The fold has no opinion about order, and the
    review card renders these in sequence — a departing person past the second collapses to a
    chip, so which one that is depends on this."""
    rows = display_rows(
        Roster(
            people=(
                Person(id="p2", name="Zoe Vance"),
                Person(id="p1", name="Ann Lee"),
            )
        ),
        _JURISDICTION,
        TAXONOMY,
    )

    assert [row["name"] for row in rows] == ["Ann Lee", "Zoe Vance"]


@pytest.mark.unit
def test_a_post_shows_the_name_a_human_gave_it():
    """`database.posts._with_label`'s rule, which the fold cannot apply itself: naming a post
    writes a claim on the POST entity, and `database/facts.py` does not load those yet."""
    person = Person(id="p1", name="Ann Lee", memberships=(_membership(),))

    [row] = display_rows(
        Roster(people=(person,)),
        _JURISDICTION,
        TAXONOMY,
        {("org-1", "mayor", _BASE): "Position 8"},
    )

    assert row["memberships"][0]["post_label"] == "Position 8"


@pytest.mark.unit
def test_a_post_nobody_named_keeps_the_derived_label():
    person = Person(id="p1", name="Ann Lee", memberships=(_membership(),))

    [row] = display_rows(
        Roster(people=(person,)),
        _JURISDICTION,
        TAXONOMY,
        {("org-1", "council-member", _BASE): "Position 8"},
    )

    assert row["memberships"][0]["post_label"] == "Mayor"
