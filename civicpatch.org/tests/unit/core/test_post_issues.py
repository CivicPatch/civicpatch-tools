from datetime import datetime, timezone

import pytest

from core.membership_proposal import MembershipDisposition, MembershipPost, ProposedChange
from core.post_issues import (
    moved_person_issues,
    moved_person_issues_from_roster,
    organizations_nobody_was_found_in,
    organizations_nobody_was_found_in_from_roster,
    unverified_post_issues,
)
from core.projection.diff import roster_diff
from core.projection.facts import PostKey
from core.projection.people import Membership, Person
from core.projection.roster import Roster
from shared.schemas import POST_FIELD, IssueCode

_BASE = "ocd-division/country:us/state:wa/place:buckley"


def _post(**overrides) -> dict:
    return {
        "id": "post-1",
        "role_id": "council_member",
        "role_label": "Council Member",
        "division_ocdid": f"{_BASE}/council_district:3",
        **overrides,
    }


@pytest.mark.unit
def test_the_post_is_named_by_role_and_division():
    issues = unverified_post_issues([_post()])
    assert [issue.code for issue in issues] == [IssueCode.UNVERIFIED_POST]
    assert issues[0].message == "Unverified post: Council Member, District 3"


@pytest.mark.unit
def test_a_post_covering_the_whole_jurisdiction_names_no_division():
    """At-large is the jurisdiction's own division. Appending it would read as a place, not as
    the absence of one."""
    issues = unverified_post_issues([_post(role_label="Mayor", division_ocdid=_BASE)])
    assert issues[0].message == "Unverified post: Mayor"


@pytest.mark.unit
def test_nothing_unverified_asks_nothing():
    assert unverified_post_issues([]) == []


def _change(disposition: MembershipDisposition) -> ProposedChange:
    return ProposedChange(
        person_id="p1",
        organization_id="org-1",
        disposition=disposition,
        post=MembershipPost(
            role_id="council-president",
            role_label="Council President",
            division_ocdid=f"{_BASE}/ward:9",
            label="Council President, Ward 9",
        ),
    )


@pytest.mark.unit
def test_a_post_move_is_raised_against_the_person_and_anchored_to_the_post_field():
    """The anchor is what puts the Post row on the card at all: `post_id` is the reviewer's
    pick and is null on both sides until they make one, so a field diff sees nothing."""
    issues = moved_person_issues([_change(MembershipDisposition.MOVED)], {})
    assert [issue.code for issue in issues] == [IssueCode.MOVED_PERSON]
    assert issues[0].person_ids == ["p1"]
    assert issues[0].field == POST_FIELD
    assert issues[0].message == "Moved to Council President, Ward 9"


@pytest.mark.unit
@pytest.mark.parametrize(
    "disposition", [MembershipDisposition.UNCHANGED, MembershipDisposition.NEW, MembershipDisposition.ABSENT]
)
def test_only_a_move_raises_one(disposition: MembershipDisposition):
    """Arrivals and departures are already `new_person` and `absent_person`; raising this
    for them too would report one event twice."""
    assert moved_person_issues([_change(disposition)], {}) == []


@pytest.mark.unit
def test_a_move_names_both_posts_when_the_old_one_is_known():
    change = _change(MembershipDisposition.MOVED).model_copy(
        update={
            "from_post": MembershipPost(
                role_id="council-member",
                role_label="Council Member",
                division_ocdid=f"{_BASE}/ward:1",
                label="Council Member, Ward 1",
            )
        }
    )

    assert moved_person_issues([change], {})[0].message == (
        "Moved from Council Member, Ward 1 to Council President, Ward 9"
    )


@pytest.mark.unit
def test_a_move_the_reviewer_already_picked_is_not_raised_again():
    """The pick is the move the card already shows; the issue would be the same event twice."""
    assert moved_person_issues([_change(MembershipDisposition.MOVED)], {"p1": "post-9"}) == []


@pytest.mark.unit
def test_a_pick_for_someone_else_does_not_suppress_the_move():
    issues = moved_person_issues([_change(MembershipDisposition.MOVED)], {"other": "post-9"})

    assert [issue.person_ids for issue in issues] == [["p1"]]
def _in(organization_id: str, person_id: str, disposition: MembershipDisposition) -> ProposedChange:
    return ProposedChange(
        person_id=person_id,
        organization_id=organization_id,
        disposition=disposition,
        post=MembershipPost(
            role_id="council-member",
            role_label="Council Member",
            division_ocdid=_BASE,
            label="Council Member",
        ),
    )


_NAMES = {"council": "City Council", "mayors-office": "Office of the Mayor"}


@pytest.mark.unit
def test_an_organization_of_only_departures_is_raised():
    """Nothing publishes there, and only a person can say whether the scrape missed the page or
    the body really emptied."""
    issues = organizations_nobody_was_found_in(
        [
            _in("council", "a", MembershipDisposition.UNCHANGED),
            _in("mayors-office", "b", MembershipDisposition.ABSENT),
        ],
        _NAMES,
    )

    assert [(issue.code, issue.message) for issue in issues] == [
        (IssueCode.NOBODY_FOUND_IN_ORGANIZATION, "Nobody found in Office of the Mayor")
    ]


@pytest.mark.unit
def test_an_organization_with_anyone_left_in_it_is_not_raised():
    issues = organizations_nobody_was_found_in(
        [
            _in("council", "a", MembershipDisposition.ABSENT),
            _in("council", "b", MembershipDisposition.UNCHANGED),
        ],
        _NAMES,
    )

    assert issues == []


@pytest.mark.unit
def test_an_organization_nothing_was_proposed_for_is_not_raised():
    """Only what the proposal names can be judged: an organization with no rows is not in it."""
    assert organizations_nobody_was_found_in([], _NAMES) == []


@pytest.mark.unit
def test_an_unnamed_organization_still_reads_as_a_sentence():
    issues = organizations_nobody_was_found_in([_in("gone", "a", MembershipDisposition.ABSENT)], {})

    assert issues[0].message == "Nobody found in one organization"


# ── The same two checks over the fold's models ────────────────────────────────

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
        first_seen_at=_T,
        last_seen_at=_T,
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
