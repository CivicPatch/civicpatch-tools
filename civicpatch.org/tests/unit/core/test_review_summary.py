"""Pure — two rosters and the post issues in, the card's issue list out. No mocks.

Moved from tests/unit/services/test_review_proposal.py, which reached this rule through six mocked
loaders; the rule now lives in a pure builder, so it is tested there directly.

`build_card_summary` and its three tests went on 2026-09-24 with the proposal layer. Two of the
three ("absent", "a first scrape raises nothing to compare") are the same claims as
`test_fold_summary_flags_absent_and_new_by_id` and
`test_fold_summary_first_scrape_raises_no_new_people`, which is why they are not ported twice.
The third, the ordering, is below over `fold_card_summary`.
"""

from datetime import datetime, timezone

import pytest

from core.post_issues import unverified_post_issues
from core.projection.diff import roster_diff
from core.projection.facts import PostKey
from core.projection.people import Membership, Person
from core.projection.roster import Roster
from core.review_summary import fold_card_summary, roster_summary
from shared.schemas import Issue, IssueCode

OCDID = "ocd-jurisdiction/country:us/state:tx/place:alpha/government"


# ── The fold's own models ─────────────────────────────────────────────────────

_T = datetime(2026, 1, 1, tzinfo=timezone.utc)
_BASE = "ocd-division/country:us/state:tx/place:alpha"


def _membership(role_id="mayor", division=f"{_BASE}/council_district:1"):
    return Membership(
        post=PostKey(organization_id="org-1", role_id=role_id, division_ocdid=division),
        opened_at=_T,
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
def test_roster_checks_come_first_and_post_checks_after():
    """One list for the card; which check produced a row is not the card's business.

    This read `build_card_summary`, which took a proposed roster and a list of proposals. It
    now reads `fold_card_summary`, which takes the two rosters the fold derives, because the
    proposal layer is gone — the claim about ordering is unchanged.
    """
    post = {
        "id": "post-1",
        "role_id": "council_member",
        "role_label": "Council Member",
        "division_ocdid": f"{_BASE}/council_district:3",
    }
    published = Roster()
    proposed = Roster(people=(_fold_person("a", "Ann Lee"),))

    summary = fold_card_summary(
        published,
        proposed,
        roster_diff(published, proposed),
        read_organization_ids=set(),
        role_labels={},
        unique_role_ids=set(),
        unverified_posts=unverified_post_issues([post]),
        organization_names={},
    )

    assert all(isinstance(issue, Issue) for issue in summary.issues)
    assert [issue.code for issue in summary.issues] == [
        IssueCode.TOO_FEW_PEOPLE,
        IssueCode.UNVERIFIED_POST,
    ]
