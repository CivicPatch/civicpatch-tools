import pytest

from core.membership_proposal import Disposition, ProposedChange
from core.post_issues import (
    append_post_issues,
    disputed_post_issues,
    moved_person_issues,
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


def _change(disposition: Disposition, **overrides) -> ProposedChange:
    return ProposedChange(
        person_id="p1",
        disposition=disposition,
        role_id="council-president",
        role_label="Council President",
        division_ocdid=f"{_BASE}/ward:9",
        post_label="Council President, Ward 9",
        **overrides,
    )


@pytest.mark.unit
def test_a_seat_move_is_raised_against_the_person_and_anchored_to_the_post_field():
    """The anchor is what puts the Post row on the card at all: `post_id` is the reviewer's
    pick and is null on both sides until they make one, so a field diff sees nothing."""
    issues = moved_person_issues([_change(Disposition.MOVED)], {})
    assert [issue.code for issue in issues] == [IssueCode.MOVED_PERSON]
    assert issues[0].person_ids == ["p1"]
    assert issues[0].field == POST_FIELD
    assert issues[0].message == "Moved to Council President, Ward 9"


@pytest.mark.unit
@pytest.mark.parametrize(
    "disposition", [Disposition.UNCHANGED, Disposition.NEW, Disposition.ABSENT]
)
def test_only_a_move_raises_one(disposition: Disposition):
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


@pytest.mark.unit
def test_a_pick_the_derivation_disagrees_with_is_raised():
    """An accepted post outlives the scrape that prompted it, which is the point — but it also
    means a parser fix can no longer move that person. The disagreement is said out loud rather
    than resolved silently either way."""
    issues = disputed_post_issues(
        [_change(Disposition.UNCHANGED, post_id="post-derived")],
        {"p1": "post-picked"},
    )
    assert [issue.code for issue in issues] == [IssueCode.DISPUTED_POST]
    assert issues[0].person_ids == ["p1"]
    assert issues[0].field == POST_FIELD
    assert "Council President, Ward 9" in issues[0].message


@pytest.mark.unit
def test_a_pick_the_derivation_agrees_with_is_silent():
    """A pick names an existing post, so agreeing means `ids_by_identity` returned that same id."""
    assert (
        disputed_post_issues(
            [_change(Disposition.UNCHANGED, post_id="post-same")], {"p1": "post-same"}
        )
        == []
    )


@pytest.mark.unit
def test_a_derived_post_with_no_row_yet_still_disputes_a_pick():
    """`post_id` is None when the derivation names a post nothing holds. That cannot be what the
    reviewer picked — a pick is an existing post — so it is a real difference, not a gap."""
    issues = disputed_post_issues(
        [_change(Disposition.MOVED, post_id=None)], {"p1": "post-picked"}
    )
    assert [issue.code for issue in issues] == [IssueCode.DISPUTED_POST]


@pytest.mark.unit
def test_nobody_disputes_a_person_the_scrape_did_not_find():
    """An absent person is `absent_person`'s business. Their pick is not being contradicted —
    the scrape says nothing about them at all."""
    assert (
        disputed_post_issues(
            [_change(Disposition.ABSENT, post_id=None)], {"p1": "post-picked"}
        )
        == []
    )


@pytest.mark.unit
def test_no_pick_means_nothing_to_dispute():
    assert disputed_post_issues([_change(Disposition.MOVED)], {}) == []


@pytest.mark.unit
def test_a_move_is_silent_once_somebody_has_picked():
    """The two checks would otherwise both fire on one situation: a person the scrape wants to
    move, whose reviewer already answered. `disputed_post` is the live question then — a pick is
    the newer answer, and a checklist saying the same thing twice stops being read."""
    changes = [_change(Disposition.MOVED, post_id="post-derived")]
    assert moved_person_issues(changes, {"p1": "post-picked"}) == []
    assert [issue.code for issue in disputed_post_issues(changes, {"p1": "post-picked"})] == [
        IssueCode.DISPUTED_POST
    ]
