from datetime import datetime, timezone


import pytest

from core.post_issues import (
    moved_person_issues_from_roster,
    new_post_issues_from_roster,
    organizations_nobody_was_found_in_from_roster,
    uncertain_organization_issues_from_records,
)
from core.projection.diff import roster_diff
from core.projection.facts import PostKey, SourceRecord
from core.projection.people import Membership, Person
from core.projection.roster import Roster
from shared.schemas import POST_FIELD, IssueCode
from shared.utils.statuses import OrganizationPlacedBy

_BASE = "ocd-division/country:us/state:wa/place:buckley"
_T = datetime(2026, 1, 1, tzinfo=timezone.utc)


_ROLE_LABELS = {"council-member": "Council Member", "mayor": "Mayor"}


def _roster(*people) -> Roster:
    return Roster(people=tuple(people))


def _membership(
    role_id="council-member", division=f"{_BASE}/ward:1", organization_id="council"
) -> Membership:
    return Membership(
        post=PostKey(
            organization_id=organization_id, role_id=role_id, division_ocdid=division
        ),
        opened_at=_T,
    )


def _person(
    person_id,
    role_id="council-member",
    division=f"{_BASE}/ward:1",
    organization_id="council",
) -> Person:
    return Person(
        id=person_id,
        name=person_id,
        memberships=(_membership(role_id, division, organization_id),),
    )


@pytest.mark.unit
def test_a_move_over_the_fold_names_both_posts():
    published = _roster(_person("p1"))
    proposed = _roster(_person("p1", role_id="mayor", division=_BASE))

    issues = moved_person_issues_from_roster(
        published, proposed, roster_diff(published, proposed), _ROLE_LABELS
    )

    assert [
        (issue.code, issue.message, issue.person_ids, issue.field) for issue in issues
    ] == [
        (
            IssueCode.MOVED_PERSON,
            "Moved from Council Member, Ward 1 to Mayor",
            ["p1"],
            POST_FIELD,
        )
    ]


@pytest.mark.unit
def test_a_person_who_changed_organization_did_not_move():
    """A move is within one body; turning up in another is an absence and an arrival."""
    published = _roster(_person("p1", organization_id="council"))
    proposed = _roster(_person("p1", organization_id="mayors-office"))

    assert (
        moved_person_issues_from_roster(
            published, proposed, roster_diff(published, proposed), _ROLE_LABELS
        )
        == []
    )


@pytest.mark.unit
def test_an_organization_of_only_departures_is_raised_over_the_fold():
    issues = organizations_nobody_was_found_in_from_roster(
        _roster(_person("a"), _person("b")),
        _roster(),
        {"council"},
        {"council": "City Council"},
    )

    assert [(issue.code, issue.message) for issue in issues] == [
        (IssueCode.NOBODY_FOUND_IN_ORGANIZATION, "Nobody found in City Council")
    ]


@pytest.mark.unit
def test_an_organization_with_anyone_left_is_not_raised_over_the_fold():
    assert (
        organizations_nobody_was_found_in_from_roster(
            _roster(_person("a"), _person("b")),
            _roster(_person("b")),
            {"council"},
            {"council": "City Council"},
        )
        == []
    )


@pytest.mark.unit
def test_a_member_who_moved_to_another_organization_is_still_on_the_roster():
    """`propose` marks a departure only when the person is unseen everywhere, so a cross-body
    move raises nothing for the body they left."""
    published = _roster(_person("a", organization_id="council"))
    proposed = _roster(_person("a", organization_id="mayors-office"))

    assert (
        organizations_nobody_was_found_in_from_roster(
            published, proposed, {"council", "mayors-office"}, {"council": "City Council"}
        )
        == []
    )


@pytest.mark.unit
def test_an_organization_the_changeset_did_not_read_is_not_raised():
    assert (
        organizations_nobody_was_found_in_from_roster(
            _roster(_person("a")), _roster(), set(), {"council": "City Council"}
        )
        == []
    )


def _new_post_issues(proposed: Roster, existing: set[str], council_labels: dict[str, str]):
    return new_post_issues_from_roster(proposed, existing, {"council": council_labels}, _ROLE_LABELS, {"council": "City Council"})


@pytest.mark.unit
def test_a_post_the_scrape_fills_that_does_not_exist_yet_is_marked_new_on_the_person():
    proposed = _roster(_person("p1"))

    issues = _new_post_issues(proposed, set(), {"council-member": "Councilor"})

    assert [(issue.code, issue.person_ids, issue.field) for issue in issues] == [(IssueCode.NEW_POST, ["p1"], POST_FIELD)]
    assert issues[0].message.startswith("New post: Councilor")
    assert issues[0].message.endswith(", City Council")


@pytest.mark.unit
def test_a_new_post_whose_role_the_place_does_not_give_the_organization_says_so():
    proposed = _roster(_person("p1", role_id="mayor", division=_BASE))

    issues = _new_post_issues(proposed, set(), {"council-member": "Councilor"})

    assert issues[0].message == "New post, not in this place's law or config: Mayor, City Council"


@pytest.mark.unit
def test_a_post_that_already_exists_raises_nothing():
    proposed = _roster(_person("p1"))
    existing = {membership.post.post_id for person in proposed.people for membership in person.memberships}

    assert _new_post_issues(proposed, existing, {"council-member": "Councilor"}) == []


def _record(person_id: str, placed_by: OrganizationPlacedBy | None) -> SourceRecord:
    return SourceRecord(
        id=f"r-{person_id}",
        changeset_id="c1",
        created_at=_T,
        person_id=person_id,
        organization_id="council",
        name=person_id,
        label="Chair",
        source_url="https://x.gov/boards",
        organization_placed_by=placed_by,
    )


@pytest.mark.unit
def test_a_person_the_model_placed_is_asked_about_once_on_their_post():
    proposed = _roster(_person("p1"), _person("p2"))
    records = [_record("p1", OrganizationPlacedBy.LLM), _record("p1", OrganizationPlacedBy.LLM), _record("p2", OrganizationPlacedBy.JEV)]

    issues = uncertain_organization_issues_from_records(proposed, records, {"council": "City Council"})

    assert [(issue.code, issue.person_ids, issue.field, issue.message) for issue in issues] == [
        (IssueCode.UNCERTAIN_ORGANIZATION, ["p1"], POST_FIELD, "Organization uncertain: picked by the general model after Jev was unsure: City Council")
    ]


@pytest.mark.unit
def test_a_record_placed_by_rule_or_by_nobody_raises_nothing():
    proposed = _roster(_person("p1"), _person("p2"))
    records = [_record("p1", OrganizationPlacedBy.ROLE), _record("p2", None)]

    assert uncertain_organization_issues_from_records(proposed, records, {}) == []
