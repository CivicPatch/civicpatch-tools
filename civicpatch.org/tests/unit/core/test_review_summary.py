"""Pure — rosters, proposals and post issues in, the card's issue list out. No mocks.

Moved from tests/unit/services/test_review_proposal.py, which reached this rule through six mocked
loaders; the rule now lives in a pure builder, so it is tested there directly.
"""

import pytest

from core.post_issues import unverified_post_issues
from core.review_summary import build_card_summary
from shared.schemas import Issue, IssueCode

OCDID = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"


def _person(name: str, office: str = "Mayor") -> dict:
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "office": {"name": office, "division_ocdid": None},
        "jurisdiction_ocdid": OCDID,
    }


def _summary(published: list[dict], proposed: list[dict], unverified_posts=()):
    return build_card_summary(published, proposed, [], [], list(unverified_posts), {})


@pytest.mark.unit
def test_somebody_we_publish_and_this_scrape_missed_is_absent():
    """The baseline is the roster we publish. It used to be the pipeline's research step,
    which lived only in the workflow context — which is why the summary had to be frozen at
    ingest and could never be recomputed."""
    summary = _summary([_person("Bob Smith")], [_person("Ann Lee")])

    codes = {issue.code for issue in summary.issues}
    assert IssueCode.ABSENT_PERSON in codes
    assert IssueCode.NEW_PERSON in codes


@pytest.mark.unit
def test_a_jurisdiction_we_have_never_published_raises_nothing_to_compare():
    """A first scrape has no roster to compare with, so neither set check applies — everyone
    would be new, which would keep every such jurisdiction out of auto-publish forever.

    The checks that read the proposed roster alone still run, which is why a five-person
    roster is used here: one person would fail `too_few_people` instead."""
    roster = [_person(name) for name in ("Ann Lee", "Bo Ray", "Cy Fox", "Di Ash", "Ed Vale")]

    summary = _summary([], roster)

    codes = {issue.code for issue in summary.issues}
    assert IssueCode.ABSENT_PERSON not in codes
    assert IssueCode.NEW_PERSON not in codes


@pytest.mark.unit
def test_roster_checks_come_first_and_post_checks_after():
    """One list for the card; which check produced a row is not the card's business."""
    post = {
        "id": "post-1",
        "role_id": "council_member",
        "role_label": "Council Member",
        "division_ocdid": "ocd-division/country:us/state:tx/place:alpha/council_district:3",
    }

    summary = _summary([], [_person("Ann Lee")], unverified_post_issues([post]))

    assert all(isinstance(issue, Issue) for issue in summary.issues)
    assert [issue.code for issue in summary.issues] == [
        IssueCode.TOO_FEW_PEOPLE,
        IssueCode.UNVERIFIED_POST,
    ]
