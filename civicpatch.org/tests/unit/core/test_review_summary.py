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


def _membership(role_id="mayor", division=f"{_BASE}/council_district:1", extra_roles=()):
    return Membership(
        post=PostKey(organization_id="org-1", role_id=role_id, division_ocdid=division),
        opened_at=_T,
        extra_roles=extra_roles,
    )


def _fold_person(
    person_id, name, role_id="mayor", division=f"{_BASE}/council_district:1"
):
    return Person(
        id=person_id, name=name, memberships=(_membership(role_id, division),)
    )


def _fold_summary(
    published_people, proposed_people, unique_role_ids=frozenset(), retired_ids=frozenset()
):
    published = Roster(people=tuple(published_people))
    proposed = Roster(people=tuple(proposed_people))
    known = {person.id for person in published_people} | set(retired_ids)
    return roster_summary(
        published, proposed, roster_diff(published, proposed), known, set(unique_role_ids)
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
def test_fold_summary_a_returning_person_is_not_new():
    summary = _fold_summary(
        [_fold_person("a", "Ann Lee")],
        [_fold_person("a", "Ann Lee"), _fold_person("b", "Bob Smith")],
        retired_ids={"b"},
    )

    assert IssueCode.NEW_PERSON not in {issue.code for issue in summary.issues}


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


def _president(person_id, name, wards):
    memberships = tuple(
        _membership("member", f"{_BASE}/ward:{ward}", extra_roles=("president",)) for ward in wards
    )
    return Person(id=person_id, name=name, memberships=memberships)


def _duplicate_unique_role_issues(proposed_people):
    summary = _fold_summary([], proposed_people, unique_role_ids=frozenset({"president"}))
    return [issue for issue in summary.issues if issue.code is IssueCode.DUPLICATE_UNIQUE_ROLE]


@pytest.mark.unit
def test_fold_summary_flags_a_unique_member_role_held_twice():
    dupes = _duplicate_unique_role_issues([_president("a", "Ann Lee", [1]), _president("b", "Bob Smith", [2])])

    assert len(dupes) == 1
    assert set(dupes[0].person_ids) == {"a", "b"}


@pytest.mark.unit
def test_fold_summary_one_person_holding_a_unique_role_twice_is_no_duplicate():
    assert _duplicate_unique_role_issues([_president("a", "Ann Lee", [1, 2])]) == []


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
    published = Roster()
    proposed = Roster(people=(_fold_person("a", "Ann Lee"),))

    summary = fold_card_summary(
        published,
        proposed,
        roster_diff(published, proposed),
        known_person_ids=set(),
        read_organization_ids=set(),
        role_labels={},
        unique_role_ids=set(),
        organization_names={},
    )

    assert all(isinstance(issue, Issue) for issue in summary.issues)
    assert [issue.code for issue in summary.issues] == [IssueCode.TOO_FEW_PEOPLE]
