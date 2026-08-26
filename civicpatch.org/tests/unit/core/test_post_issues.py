import pytest

from core.post_issues import append_post_issues, unverified_post_issues
from shared.schemas import IssueCode

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
