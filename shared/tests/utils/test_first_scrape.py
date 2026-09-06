"""A jurisdiction we hold nothing for: the set checks have no roster to compare with.

Every person would otherwise raise NEW_PERSON, so a first scrape could never auto-publish —
all 39 Washington counties, and every jurisdiction whose data predates the changesets, would
queue for a reviewer with nothing for them to compare against.
"""

import pytest

from shared.schemas import IssueCode
from shared.utils.review_utils import ReviewInputs, build_review_summary

pytestmark = pytest.mark.unit


def _person(name, **over):
    return {"name": name, "phones": [], "emails": [], "urls": [], "other_names": [], **over}


def _roster(*names):
    return [_person(name) for name in names]


def _summary(before, after):
    return build_review_summary(before, after, ReviewInputs())


def _codes(summary):
    return {issue.code for issue in summary["issues"]}


_FOUND = _roster("Rich Elliott", "Nancy Goodloe", "David Miller", "Delano Palmer",
                 "Sarah Beauchamp")


def test_a_first_scrape_raises_nothing_to_review():
    assert _codes(_summary([], _FOUND)) == set()


def test_a_first_scrape_still_fails_a_thin_roster():
    """Suppressing NEW_PERSON is not a rubber stamp — the checks that read the proposed roster
    alone still run."""
    assert IssueCode.TOO_FEW_PEOPLE in _codes(_summary([], _roster("Rich Elliott")))


def test_the_next_scrape_surfaces_someone_new():
    after = _FOUND + [_person("Joshua Thompson")]

    issues = [i for i in _summary(_FOUND, after)["issues"] if i.code == IssueCode.NEW_PERSON]

    assert [i.message for i in issues] == ["New person found: Joshua Thompson"]


def test_the_next_scrape_surfaces_someone_missing():
    issues = [
        i for i in _summary(_FOUND, _FOUND[:-1])["issues"]
        if i.code == IssueCode.ABSENT_PERSON
    ]

    assert len(issues) == 1
