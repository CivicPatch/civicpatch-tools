"""Pure — two rosters and the membership proposals in, what changed out. No mocks."""

import pytest

from core.membership_label import derive_post_label
from core.membership_proposal import ExistingMembership, MembershipPost, propose
from core.post_derivation import DerivedMembership, DerivedPost
from core.roster_diff import (
    UNCHANGED_NOTE,
    ChangeCounts,
    DiffType,
    count_changes,
    likely_same_people,
    person_diffs,
    person_notes,
)

_BASE = "ocd-division/country:us/state:zz/place:testville"
_COUNCIL = "org-council"
_SCHOOL_BOARD = "org-school"


def _person(person_id, name, **fields):
    return {"id": person_id, "name": name, **fields}


def _post(division_ocdid, *person_ids, organization_id=_COUNCIL):
    return DerivedPost(
        organization_id=organization_id,
        role_id="council-member",
        role_label="Council Member",
        division_ocdid=division_ocdid,
        headcount=len(person_ids),
        members=[DerivedMembership(person_id=person_id) for person_id in person_ids],
    )


def _held(person_id, division_ocdid, organization_id=_COUNCIL):
    return ExistingMembership(
        id=f"membership-{person_id}",
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:zz/place:testville/government",
        person_id=person_id,
        organization_id=organization_id,
        post=MembershipPost(
            id=f"post-{division_ocdid}",
            role_id="council-member",
            role_label="Council Member",
            division_ocdid=division_ocdid,
            label=derive_post_label("Council Member", division_ocdid),
        ),
    )


@pytest.mark.unit
def test_someone_not_published_is_added():
    [diff] = person_diffs([], [_person("p1", "Ana Reyes")])

    assert (diff.person_id, diff.type) == ("p1", DiffType.ADDED)


@pytest.mark.unit
def test_a_changed_phone_is_a_change_on_that_field():
    before = _person("p1", "Ana Reyes", phones=["555-0100"])
    after = _person("p1", "Ana Reyes", phones=["555-0199"])

    [diff] = person_diffs([before], [after])

    assert diff.type is DiffType.CHANGED
    assert diff.fields == ["phones"]


@pytest.mark.unit
def test_lists_compare_as_case_folded_sets_like_the_card():
    before = _person("p1", "Ana Reyes", emails=["Ana@Town.gov", "clerk@town.gov"])
    after = _person("p1", " Ana Reyes ", emails=["clerk@town.gov ", "ana@town.gov"])

    assert person_diffs([before], [after]) == []


@pytest.mark.unit
def test_a_new_photo_or_source_is_not_a_change():
    before = _person("p1", "Ana Reyes", image="a.jpg", source_urls=["https://a"])
    after = _person("p1", "Ana Reyes", image="b.jpg", source_urls=["https://b"])

    assert person_diffs([before], [after]) == []


@pytest.mark.unit
def test_absent_counts_memberships_in_an_organization_read():
    proposals = propose(
        [_post(f"{_BASE}/ward:1", "p1")],
        [_held("p1", f"{_BASE}/ward:1"), _held("p2", f"{_BASE}/ward:2")],
        [_COUNCIL],
    )

    assert count_changes([], proposals).absent_memberships == 1


@pytest.mark.unit
def test_a_membership_in_an_organization_not_read_is_not_absent():
    """The school board was never read by this import, so its member is not absent."""
    proposals = propose(
        [_post(f"{_BASE}/ward:1", "p1")],
        [_held("p1", f"{_BASE}/ward:1"), _held("s1", _BASE, organization_id=_SCHOOL_BOARD)],
        [_COUNCIL],
    )

    assert count_changes([], proposals).absent_memberships == 0


@pytest.mark.unit
def test_counts_people_and_absent_memberships():
    published = [_person("p1", "Ana Reyes", phones=["1"]), _person("p2", "Bo Chen")]
    proposed = [_person("p1", "Ana Reyes", phones=["2"]), _person("p3", "Cy Dunn")]
    proposals = propose(
        [_post(f"{_BASE}/ward:1", "p1"), _post(f"{_BASE}/ward:3", "p3")],
        [_held("p1", f"{_BASE}/ward:1"), _held("p2", f"{_BASE}/ward:2")],
        [_COUNCIL],
    )

    assert count_changes(person_diffs(published, proposed), proposals) == ChangeCounts(
        added_people=1, changed_people=1, absent_memberships=1
    )


def _label(division_ocdid):
    return derive_post_label("Council Member", division_ocdid)


@pytest.mark.unit
def test_a_new_person_notes_that_first_then_their_post():
    proposals = propose([_post(f"{_BASE}/ward:3", "p3")], [], [_COUNCIL])

    notes = person_notes(["p3"], person_diffs([], [_person("p3", "Cy Dunn")]), proposals, {})

    assert notes == {"p3": f"new person; new post: {_label(f'{_BASE}/ward:3')}"}


@pytest.mark.unit
def test_a_move_comes_before_changed_fields():
    published = [_person("p1", "Ana Reyes", phones=["1"], emails=["a@x.gov"])]
    proposed = [_person("p1", "Ana Reyes", phones=["2"], emails=["b@x.gov"])]
    proposals = propose(
        [_post(f"{_BASE}/ward:2", "p1")], [_held("p1", f"{_BASE}/ward:1")], [_COUNCIL]
    )

    notes = person_notes(["p1"], person_diffs(published, proposed), proposals, {})

    assert notes["p1"] == (
        f"moved from {_label(f'{_BASE}/ward:1')} to {_label(f'{_BASE}/ward:2')}; "
        "changed: emails, phones"
    )


@pytest.mark.unit
def test_someone_the_import_leaves_as_they_are_is_unchanged():
    person = _person("p1", "Ana Reyes")
    proposals = propose(
        [_post(f"{_BASE}/ward:1", "p1")], [_held("p1", f"{_BASE}/ward:1")], [_COUNCIL]
    )

    assert person_notes(["p1"], person_diffs([person], [person]), proposals, {}) == {
        "p1": UNCHANGED_NOTE
    }


def _turnover(published: list[dict], proposed: list[dict]):
    """Everyone published held a ward; everyone proposed is seated in one."""
    proposals = propose(
        [_post(f"{_BASE}/ward:{index}", person["id"]) for index, person in enumerate(proposed)],
        [_held(person["id"], f"{_BASE}/ward:{index}") for index, person in enumerate(published)],
        [_COUNCIL],
    )
    return person_diffs(published, proposed), proposals


@pytest.mark.unit
def test_an_added_and_an_absent_person_sharing_a_surname_may_be_one():
    """Ferndale, 2026-09-18: the sheet said Jennifer, we publish her as Jenny."""
    published = [_person("p1", "Ana Reyes"), _person("p2", "Jenny Fisk-Becker")]
    proposed = [_person("p1", "Ana Reyes"), _person("p3", "Jennifer Fisk-Becker")]
    diffs, proposals = _turnover(published, proposed)

    assert likely_same_people(published, proposed, diffs, proposals) == {
        "p3": "Jenny Fisk-Becker",
        "p2": "Jennifer Fisk-Becker",
    }


@pytest.mark.unit
def test_two_absent_people_sharing_the_surname_make_no_pair():
    published = [_person("p1", "Ann Smith"), _person("p2", "Bob Smith")]
    proposed = [_person("p3", "Robert Smith")]
    diffs, proposals = _turnover(published, proposed)

    assert likely_same_people(published, proposed, diffs, proposals) == {}


@pytest.mark.unit
def test_a_likely_pair_tells_the_volunteer_how_to_link_them():
    published = [_person("p2", "Jenny Fisk-Becker")]
    proposed = [_person("p3", "Jennifer Fisk-Becker")]
    diffs, proposals = _turnover(published, proposed)
    likely = likely_same_people(published, proposed, diffs, proposals)

    notes = person_notes(["p3"], diffs, proposals, likely)

    assert notes["p3"].startswith(
        "new person; may be Jenny Fisk-Becker: add that name to other_names to link them"
    )
