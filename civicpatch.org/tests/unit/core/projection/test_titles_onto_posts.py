"""Plan 2's 2.5 and 2.6d: only a role elected by voters is a post's role, and a label naming only
roles the organization's members elect ("Vice Mayor", "Chair") is a member's, on the
organization's Member post at the division it names.

Labels are the dry run's real ones (Alameda, Bakersfield, Antioch).
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus, SelectionMethod
from shared.utils.taxonomy import MEMBER_ROLE_ID, build_taxonomy

from core.projection.facts import PostKey, SourceRecord
from core.projection.posts import parse_labels, post_keys

pytestmark = pytest.mark.unit

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
JURISDICTION = "ocd-jurisdiction/country:us/state:ca/place:alpha/government"
BASE = "ocd-division/country:us/state:ca/place:alpha"
COUNCIL = "council"


def _role(id_: str, label: str, priority: int, method: SelectionMethod, aliases: list[str] | None = None) -> Role:
    return Role(
        id=id_, label=label, status=RoleStatus.ACTIVE, aliases=aliases or [], priority=priority, selection_method=method
    )


TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            _role("mayor", "Mayor", 0, SelectionMethod.ELECTED_BY_VOTERS),
            _role("vice-mayor", "Vice Mayor", 1, SelectionMethod.ELECTED_BY_MEMBERS),
            _role("mayor-pro-tempore", "Mayor Pro Tempore", 2, SelectionMethod.ELECTED_BY_MEMBERS, ["mayor pro tem"]),
            _role(MEMBER_ROLE_ID, "Member", 3, SelectionMethod.ELECTED_BY_VOTERS, ["Council Member", "Select Board Member", "Trustee"]),
            _role("city-manager", "City Manager", 4, SelectionMethod.APPOINTED),
        ]
    )
)


def _record(person_id: str, label: str) -> SourceRecord:
    return SourceRecord(
        id=f"{person_id}-{label}",
        changeset_id="c1",
        created_at=_T + timedelta(minutes=1),
        person_id=person_id,
        organization_id=COUNCIL,
        name=person_id,
        label=label,
        source_url="https://example.gov/council",
    )


def _post(role_id: str, division: str = BASE) -> PostKey:
    return PostKey(organization_id=COUNCIL, role_id=role_id, division_ocdid=division)


def _posts(*labels: str) -> set[PostKey]:
    return set(post_keys([_record(f"p{i}", label) for i, label in enumerate(labels)], JURISDICTION, TAXONOMY))


def test_a_label_naming_both_roles_is_on_the_post_elected_by_voters():
    assert _posts("Mayor Pro Tem, District 3 Council Member") == {_post(MEMBER_ROLE_ID, BASE + "/council_district:3")}


def test_the_role_elected_by_members_stays_on_the_membership():
    _, details = parse_labels([_record("p0", "Mayor Pro Tem, District 3 Council Member")], JURISDICTION, TAXONOMY)

    assert details.extra_roles == ("mayor-pro-tempore",)


def test_a_vice_mayor_is_a_member_at_the_division_the_label_names():
    assert _posts("Vice Mayor Ward 7") == {_post(MEMBER_ROLE_ID, BASE + "/ward:7")}


def test_a_vice_mayor_naming_no_division_is_a_member_at_large():
    assert _posts("Vice Mayor") == {_post(MEMBER_ROLE_ID)}


def test_every_local_name_for_a_member_is_the_one_member_post():
    assert _posts("Council Member", "Select Board Member", "Trustee") == {_post(MEMBER_ROLE_ID)}


def test_an_appointed_role_keeps_its_own_post():
    assert _posts("City Manager") == {_post("city-manager")}


def test_a_role_elected_by_members_wins_over_an_appointed_one_whatever_the_config_order():
    taxonomy = build_taxonomy(
        RoleConfig(
            roles=[
                _role("city-manager", "City Manager", 0, SelectionMethod.APPOINTED),
                _role("vice-mayor", "Vice Mayor", 1, SelectionMethod.ELECTED_BY_MEMBERS),
            ]
        )
    )

    post, _ = parse_labels([_record("p0", "Vice Mayor and City Manager")], JURISDICTION, taxonomy)

    assert post == _post(MEMBER_ROLE_ID)


def test_a_mayor_is_still_a_mayor():
    assert _posts("Mayor") == {_post("mayor")}
