"""Plan 2's step 2.5: only a role elected by voters is a post's role, and a role elected by the
organization's members ("Vice Mayor") stays on the membership of its holder's post.

Labels are the dry run's real ones (Alameda, Bakersfield, Antioch). Posts come from `post_keys`,
which reads each organization's post role off everyone's labels, as the fold does.
"""

from datetime import datetime, timedelta, timezone

import pytest
from shared.schemas import Role, RoleConfig, RoleStatus, SelectionMethod
from shared.utils.taxonomy import build_taxonomy

from core.projection.facts import PostKey, SourceRecord
from core.projection.posts import PostRole, organization_post_roles, parse_labels, post_keys

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
            _role("council-member", "Council Member", 3, SelectionMethod.ELECTED_BY_VOTERS),
            _role("city-manager", "City Manager", 4, SelectionMethod.APPOINTED),
        ]
    )
)


def _record(person_id: str, label: str, minutes: int = 0) -> SourceRecord:
    return SourceRecord(
        id=f"{person_id}-{minutes}",
        changeset_id="c1",
        created_at=_T + timedelta(minutes=minutes),
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
    posts = _posts("Mayor Pro Tem, District 3 Council Member", "District 4 Council Member")

    assert _post("council-member", BASE + "/council_district:3") in posts


def test_the_role_elected_by_members_stays_on_the_membership():
    records = [_record("p0", "Mayor Pro Tem, District 3 Council Member")]

    _, details = parse_labels(records, JURISDICTION, TAXONOMY, {})

    assert details.extra_roles == ("mayor-pro-tempore",)


def test_a_vice_mayor_with_a_division_is_on_that_divisions_post():
    posts = _posts("Vice Mayor Ward 7", "Council Member Ward 6")

    assert _post("council-member", BASE + "/ward:7") in posts


def test_a_vice_mayor_on_an_at_large_council_is_on_the_post_at_large():
    posts = _posts("Vice Mayor", "Council Member", "Council Member")

    assert posts == {_post("council-member")}


def test_a_vice_mayor_on_a_council_with_divisions_and_none_named_keeps_its_post():
    posts = _posts("Mayor Pro Tem", "District 1 Council Member", "District 2 Council Member")

    assert _post("mayor-pro-tempore") in posts


def test_an_appointed_role_never_moves_onto_a_post_elected_by_voters():
    posts = _posts("City Manager", "Council Member", "Council Member")

    assert _post("city-manager") in posts


def test_a_role_elected_by_members_wins_over_an_appointed_one_whatever_the_config_order():
    taxonomy = build_taxonomy(
        RoleConfig(
            roles=[
                _role("city-manager", "City Manager", 0, SelectionMethod.APPOINTED),
                _role("vice-mayor", "Vice Mayor", 1, SelectionMethod.ELECTED_BY_MEMBERS),
            ]
        )
    )

    post, _ = parse_labels([_record("p0", "Vice Mayor and City Manager")], JURISDICTION, taxonomy, {})

    assert post == _post("vice-mayor")


def test_a_vice_mayor_with_no_post_role_beside_it_keeps_its_post():
    assert _posts("Vice Mayor") == {_post("vice-mayor")}


def test_the_post_role_is_the_one_most_people_hold_not_a_lone_mayor():
    records = [_record("p0", "Mayor"), *(_record(f"p{i}", "Council Member") for i in range(1, 5))]

    assert organization_post_roles(records, JURISDICTION, TAXONOMY) == {
        COUNCIL: PostRole(role="Council Member", has_divisions=False)
    }


def test_the_post_role_has_divisions_when_a_holder_names_one():
    records = [_record("p0", "District 1 Council Member"), _record("p1", "Council Member")]

    assert organization_post_roles(records, JURISDICTION, TAXONOMY)[COUNCIL].has_divisions


def test_the_post_role_is_read_from_each_persons_newest_labels():
    older = _record("p0", "Council Member", minutes=0)
    newer = _record("p0", "Mayor", minutes=5).model_copy(update={"changeset_id": "c2"})

    assert organization_post_roles([older, newer], JURISDICTION, TAXONOMY)[COUNCIL].role == "Mayor"
