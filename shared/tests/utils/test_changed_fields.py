"""The sixth review check: a field moving on someone who is in both rosters.

The other five all read the *set* of people. Ellensburg auto-published under "the roster was
re-confirmed, nothing to review" while dropping an email, replacing every direct line with the
switchboard, and rewriting an image url — same seven councillors in and out, so zero issues.
"""

import pytest

from shared.schemas import IssueCode
from shared.utils.review_utils import ReviewInputs, build_review_summary

pytestmark = pytest.mark.unit

_FIELDS = ["name", "phones", "emails"]


def _person(name="Rich Elliott", **over):
    return {"name": name, "phones": [], "emails": [], "urls": [], "other_names": [], **over}


def _summary(before, after, fields=_FIELDS):
    return build_review_summary(before, after, ReviewInputs(changed_field_names=fields))


def _changed(summary):
    return [i for i in summary["issues"] if i.code == IssueCode.CHANGED_FIELD]


def test_the_same_roster_with_the_same_values_raises_nothing():
    assert _changed(_summary([_person()], [_person()])) == []


def test_a_dropped_email_is_surfaced():
    before = [_person(emails=["rich.elliott@ci.ellensburg.wa.us"])]
    after = [_person(emails=[])]

    issues = _changed(_summary(before, after))

    assert [i.field for i in issues] == ["emails"]


def test_a_switchboard_number_replacing_a_direct_line_is_surfaced():
    issues = _changed(_summary([_person(phones=["509-962-7224"])], [_person(phones=["509-962-7200"])]))

    assert [i.field for i in issues] == ["phones"]


def test_reordering_a_list_is_not_a_change():
    """Order churns as the scraper reads pages in a different sequence."""
    before = [_person(phones=["a", "b"])]
    after = [_person(phones=["b", "a"])]

    assert _changed(_summary(before, after)) == []


def test_a_new_person_is_not_reported_as_a_field_change():
    """That is `_check_new_people`'s job; reporting both says the same thing twice."""
    issues = _changed(_summary([], [_person(emails=["x@y.gov"])]))

    assert issues == []


def test_nothing_is_surfaced_when_no_fields_are_requested():
    """`shared` cannot import cp.org's field list, so an empty list means the caller did not
    pass one — silence is the safe reading, not "every field"."""
    before = [_person(phones=["a"])]
    after = [_person(phones=["b"])]

    assert _changed(_summary(before, after, fields=[])) == []


def test_the_issue_names_the_field_and_the_person():
    issues = _changed(_summary([_person(emails=["a@x.gov"])], [_person(emails=["b@x.gov"])]))

    assert issues[0].field == "emails"
    assert "Rich Elliott" in issues[0].message


def test_only_who_this_is_and_how_to_reach_them_is_surfaced():
    """Everything else is out for its own reason: `image` is adjudicated on the card anyway,
    `other_names` is merged forward so a scrape only adds, `urls`/`source_urls`/the dates change
    between scrapes by design, and `post_id` already raises `moved_person`/`disputed_post`."""
    from core.people_edits import EDITABLE_FIELDS, SURFACED_FIELDS

    assert set(SURFACED_FIELDS) == {"name", "phones", "emails"}
    assert set(SURFACED_FIELDS) < set(EDITABLE_FIELDS)
