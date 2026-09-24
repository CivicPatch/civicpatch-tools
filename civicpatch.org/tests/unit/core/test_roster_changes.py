"""Pure — two sides of a card in, what a human is told changed out. No mocks.

Ported from `test_roster_diff.py` on 2026-09-24. Each test's claim is unchanged; what moved is
the input. It used to take a roster plus the membership proposals `propose()` computed against
what we already held; it now takes the two sides `card_rows` presents, because the fold already
answers who holds what and a second membership comparison could disagree with it.
"""

import pytest

from core.membership_label import derive_post_label
from core.roster_changes import (
    UNCHANGED_NOTE,
    ChangeCounts,
    ChangeKind,
    changes_of,
    count_changes,
    likely_same_people,
    person_notes,
    proposal_counts,
)

_BASE = "ocd-division/country:us/state:zz/place:testville"
_COUNCIL = "org-council"
_SCHOOL_BOARD = "org-school"


def _label(division_ocdid):
    return derive_post_label("Council Member", division_ocdid)


def _office(division_ocdid, organization_id=_COUNCIL):
    return {
        "organization_id": organization_id,
        "post_id": f"post-{organization_id}-{division_ocdid}",
        "post_label": _label(division_ocdid),
    }


def _person(person_id, name, *offices, **fields):
    return {"id": person_id, "name": name, "memberships": list(offices), **fields}


def _change(published, proposed, person_id):
    return next(
        change
        for change in changes_of(published, proposed)
        if change.person_id == person_id
    )


@pytest.mark.unit
def test_someone_not_published_is_added():
    [change] = changes_of([], [_person("p1", "Ana Reyes")])

    assert (change.person_id, change.kind) == ("p1", ChangeKind.ADDED)


@pytest.mark.unit
def test_a_changed_phone_is_a_change_on_that_field():
    before = _person("p1", "Ana Reyes", phones=["555-0100"])
    after = _person("p1", "Ana Reyes", phones=["555-0199"])

    [change] = changes_of([before], [after])

    assert change.kind is ChangeKind.CHANGED
    assert change.fields == ["phones"]


@pytest.mark.unit
def test_lists_compare_as_case_folded_sets_like_the_card():
    before = _person("p1", "Ana Reyes", emails=["Ana@Town.gov", "clerk@town.gov"])
    after = _person("p1", " Ana Reyes ", emails=["clerk@town.gov ", "ana@town.gov"])

    [change] = changes_of([before], [after])

    assert change.kind is ChangeKind.UNCHANGED


@pytest.mark.unit
def test_a_new_photo_or_source_is_not_a_change():
    before = _person("p1", "Ana Reyes", image="a.jpg", source_urls=["https://a"])
    after = _person("p1", "Ana Reyes", image="b.jpg", source_urls=["https://b"])

    [change] = changes_of([before], [after])

    assert change.fields == []


@pytest.mark.unit
def test_somebody_dropped_from_their_only_office_is_absent():
    published = [_person("p1", "Ana Reyes", _office(f"{_BASE}/ward:1"))]

    [change] = changes_of(published, [])

    assert change.kind is ChangeKind.ABSENT
    assert change.listed is False
    assert count_changes([change]).absent_memberships == 1


@pytest.mark.unit
def test_an_office_both_sides_hold_is_not_absent():
    """This verified that `propose`'s `organizations_read` kept an unread organization's member
    off the absent list. The bound moved into the fold: an organization a changeset never read
    still holds its member on the proposed side, so there is nothing here to call absent."""
    school = _office(_BASE, organization_id=_SCHOOL_BOARD)
    published = [_person("s1", "Sam Ward", school)]
    proposed = [_person("s1", "Sam Ward", school)]

    assert count_changes(changes_of(published, proposed)).absent_memberships == 0


@pytest.mark.unit
def test_counts_people_and_absent_memberships():
    published = [
        _person("p1", "Ana Reyes", _office(f"{_BASE}/ward:1"), phones=["1"]),
        _person("p2", "Bo Chen", _office(f"{_BASE}/ward:2")),
    ]
    proposed = [
        _person("p1", "Ana Reyes", _office(f"{_BASE}/ward:1"), phones=["2"]),
        _person("p3", "Cy Dunn", _office(f"{_BASE}/ward:3")),
    ]

    counts = proposal_counts(changes_of(published, proposed))

    assert counts.people == 2
    assert counts.change_counts == ChangeCounts(
        added_people=1, changed_people=1, absent_memberships=1
    )


@pytest.mark.unit
def test_a_new_person_notes_that_first_then_their_post():
    proposed = [_person("p3", "Cy Dunn", _office(f"{_BASE}/ward:3"))]

    changes = changes_of([], proposed)

    assert person_notes(changes, {}) == {
        "p3": f"new person; new post: {_label(f'{_BASE}/ward:3')}"
    }


@pytest.mark.unit
def test_a_move_comes_before_changed_fields():
    published = [
        _person(
            "p1", "Ana Reyes", _office(f"{_BASE}/ward:1"), phones=["1"], emails=["a@x.gov"]
        )
    ]
    proposed = [
        _person(
            "p1", "Ana Reyes", _office(f"{_BASE}/ward:2"), phones=["2"], emails=["b@x.gov"]
        )
    ]

    notes = person_notes(changes_of(published, proposed), {})

    assert notes["p1"] == (
        f"moved from {_label(f'{_BASE}/ward:1')} to {_label(f'{_BASE}/ward:2')}; "
        "changed: emails, phones"
    )


@pytest.mark.unit
def test_a_move_is_within_one_organization_not_across_two():
    """Holding an office in a second organization is not a move out of the first — somebody
    holds one office per organization, and these are two."""
    published = [_person("p1", "Ana Reyes", _office(f"{_BASE}/ward:1"))]
    proposed = [
        _person(
            "p1",
            "Ana Reyes",
            _office(f"{_BASE}/ward:1"),
            _office(_BASE, organization_id=_SCHOOL_BOARD),
        )
    ]

    change = _change(published, proposed, "p1")

    assert change.kind is ChangeKind.NEW_POST
    assert [office.organization_id for office in change.offices] == [_SCHOOL_BOARD]


@pytest.mark.unit
def test_someone_the_import_leaves_as_they_are_is_unchanged():
    person = _person("p1", "Ana Reyes", _office(f"{_BASE}/ward:1"))

    assert person_notes(changes_of([person], [person]), {}) == {"p1": UNCHANGED_NOTE}


def _turnover(published: list[dict], proposed: list[dict]):
    """Everyone published held a ward; everyone proposed is seated in one."""
    return changes_of(
        [
            _person(person["id"], person["name"], _office(f"{_BASE}/ward:{index}"))
            for index, person in enumerate(published)
        ],
        [
            _person(person["id"], person["name"], _office(f"{_BASE}/ward:{index}"))
            for index, person in enumerate(proposed)
        ],
    )


@pytest.mark.unit
def test_an_added_and_an_absent_person_sharing_a_surname_may_be_one():
    """Ferndale, 2026-09-18: the sheet said Jennifer, we publish her as Jenny."""
    published = [_person("p1", "Ana Reyes"), _person("p2", "Jenny Fisk-Becker")]
    proposed = [_person("p1", "Ana Reyes"), _person("p3", "Jennifer Fisk-Becker")]

    assert likely_same_people(_turnover(published, proposed)) == {
        "p3": "Jenny Fisk-Becker",
        "p2": "Jennifer Fisk-Becker",
    }


@pytest.mark.unit
def test_two_absent_people_sharing_the_surname_make_no_pair():
    published = [_person("p1", "Ann Smith"), _person("p2", "Bob Smith")]
    proposed = [_person("p3", "Robert Smith")]

    assert likely_same_people(_turnover(published, proposed)) == {}


@pytest.mark.unit
def test_a_likely_pair_tells_the_volunteer_how_to_link_them():
    published = [_person("p2", "Jenny Fisk-Becker")]
    proposed = [_person("p3", "Jennifer Fisk-Becker")]
    changes = _turnover(published, proposed)

    notes = person_notes(changes, likely_same_people(changes))

    assert notes["p3"].startswith(
        "new person; may be Jenny Fisk-Becker: add that name to other_names to link them"
    )
