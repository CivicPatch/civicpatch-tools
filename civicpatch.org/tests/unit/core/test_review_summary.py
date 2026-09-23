"""Pure — rosters, proposals and post issues in, the card's issue list out. No mocks.

Moved from tests/unit/services/test_review_proposal.py, which reached this rule through six mocked
loaders; the rule now lives in a pure builder, so it is tested there directly.
"""

from datetime import datetime, timezone

import pytest

from core.post_issues import unverified_post_issues
from core.projection.diff import roster_diff
from core.projection.facts import PostKey
from core.projection.people import Membership, Person
from core.projection.roster import Roster
from core.review_summary import build_card_summary, roster_summary
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


# ── The fold's own models ─────────────────────────────────────────────────────

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_BASE = "ocd-division/country:us/state:tx/place:alpha"


def _membership(role_id="mayor", division=f"{_BASE}/council_district:1"):
    return Membership(
        post=PostKey(organization_id="org-1", role_id=role_id, division_ocdid=division),
        first_seen_at=_T,
        last_seen_at=_T,
    )


def _fold_person(
    person_id, name, role_id="mayor", division=f"{_BASE}/council_district:1"
):
    return Person(
        id=person_id, name=name, memberships=(_membership(role_id, division),)
    )


def _fold_summary(published_people, proposed_people, unique_role_ids=frozenset()):
    published = Roster(people=tuple(published_people))
    proposed = Roster(people=tuple(proposed_people))
    return roster_summary(
        published, proposed, roster_diff(published, proposed), set(unique_role_ids)
    )


@pytest.mark.unit
def test_fold_summary_flags_absent_and_new_by_id():
    summary = _fold_summary(
        [_fold_person("a", "Ann Lee")], [_fold_person("b", "Bob Smith")]
    )

    codes = {issue.code for issue in summary.issues}
    assert {IssueCode.ABSENT_PERSON, IssueCode.NEW_PERSON} <= codes


@pytest.mark.unit
def test_fold_summary_first_scrape_raises_no_new_people():
    summary = _fold_summary([], [_fold_person(f"p{i}", f"P{i}") for i in range(5)])

    codes = {issue.code for issue in summary.issues}
    assert IssueCode.NEW_PERSON not in codes
    assert IssueCode.ABSENT_PERSON not in codes


@pytest.mark.unit
def test_fold_summary_flags_too_few():
    summary = _fold_summary([], [_fold_person("a", "Ann Lee")])

    assert IssueCode.TOO_FEW_PEOPLE in {issue.code for issue in summary.issues}


@pytest.mark.unit
def test_fold_summary_flags_a_changed_name():
    summary = _fold_summary(
        [_fold_person("a", "Ann Lee")], [_fold_person("a", "Anne Lee")]
    )

    changed = [issue for issue in summary.issues if issue.code is IssueCode.CHANGED_FIELD]
    assert [(issue.field, issue.person_ids) for issue in changed] == [("name", ["a"])]


@pytest.mark.unit
def test_fold_summary_flags_duplicate_unique_roles():
    summary = _fold_summary(
        [],
        [_fold_person("a", "Ann Lee"), _fold_person("b", "Bob Smith")],
        unique_role_ids={"mayor"},
    )

    dupes = [
        issue for issue in summary.issues if issue.code is IssueCode.DUPLICATE_UNIQUE_ROLE
    ]
    assert len(dupes) == 1
    assert set(dupes[0].person_ids) == {"a", "b"}


@pytest.mark.unit
def test_fold_summary_flags_a_division_gap():
    summary = _fold_summary(
        [],
        [
            _fold_person("a", "Ann Lee", division=f"{_BASE}/council_district:1"),
            _fold_person("b", "Bob Smith", division=f"{_BASE}/council_district:3"),
        ],
    )

    gaps = [
        issue for issue in summary.issues if issue.code is IssueCode.DIVISION_NUMBERING_GAP
    ]
    assert [issue.message for issue in gaps] == ["Missing council district 2"]


@pytest.mark.unit
def test_fold_summary_people_by_source_is_a_name_union():
    summary = _fold_summary(
        [_fold_person("a", "Ann Lee")],
        [_fold_person("a", "Ann Lee"), _fold_person("b", "Bob Smith")],
    )

    assert [
        (row.name, row.in_research, row.in_data) for row in summary.people_by_source
    ] == [("Ann Lee", True, True), ("Bob Smith", False, True)]


@pytest.mark.unit
def test_both_summaries_agree_while_both_are_live():
    """The card reads the fold; batch review still reads the dicts (§19.3, option A). Until
    step 2 deletes one, the same changeset must raise the same issues on either page."""
    dicts = _summary([_person("Ann Lee")], [_person("Bob Smith")])
    fold = _fold_summary(
        [_fold_person("ann-lee", "Ann Lee", division=_BASE)],
        [_fold_person("bob-smith", "Bob Smith", division=_BASE)],
    )

    assert sorted(issue.code for issue in fold.issues) == sorted(
        issue.code for issue in dicts.issues
    )
    assert [
        (row.name, row.in_research, row.in_data) for row in fold.people_by_source
    ] == [(row.name, row.in_research, row.in_data) for row in dicts.people_by_source]
