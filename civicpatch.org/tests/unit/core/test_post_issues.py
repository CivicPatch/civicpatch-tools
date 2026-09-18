import pytest

from core.membership_proposal import MembershipDisposition, MembershipPost, ProposedChange
from core.post_issues import (
    append_post_issues,
    moved_person_issues,
    organizations_nobody_was_found_in,
    unverified_post_issues,
)
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
def test_stored_issues_come_first_and_post_issues_after():
    summary = {"notes": "ok", "issues": [{"code": "too_few_people", "message": "3"}]}
    merged = append_post_issues(summary, unverified_post_issues([_post()]))
    assert merged["notes"] == "ok"
    assert [issue["code"] for issue in merged["issues"]] == [
        "too_few_people",
        "unverified_post",
    ]


@pytest.mark.unit
def test_a_summary_with_no_issues_key_still_merges():
    """`review_json` is `{}` for a scrape whose summary build raised — the card must still
    show what the posts say rather than 500 on a missing key."""
    merged = append_post_issues({}, unverified_post_issues([_post()]))
    assert len(merged["issues"]) == 1


@pytest.mark.unit
def test_a_summary_nothing_was_computed_for_is_left_alone():
    assert append_post_issues({"issues": []}, []) == {"issues": []}




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
