import pytest

from core.membership_label import derive_post_label
from core.membership_proposal import (
    ExistingMembership,
    MembershipDisposition,
    MembershipPost,
    nothing_to_review,
    propose,
    surfaces_for_review,
)
from core.post_derivation import DerivedMembership, DerivedPost

# Pure — a scrape's derivation and what we already hold, in; the difference, out. No taxonomy
# and no database, because the diff is only about which post a person is in.

_BASE = "ocd-division/country:us/state:zz/place:testville"
_COUNCIL = "org-1"
_MAYORS_OFFICE = "org-2"
_WARD_3 = f"{_BASE}/ward:3"


def _propose(derived, existing, organizations_read=(_COUNCIL, _MAYORS_OFFICE)):
    """Both organizations read unless a test says otherwise, which is what every case below
    assumes when it expects an absence."""
    return propose(derived, existing, list(organizations_read))


def _post(role_id, division_ocdid, *person_ids, label=None, organization_id=_COUNCIL):
    return DerivedPost(
        organization_id=organization_id,
        role_id=role_id,
        # Required, not defaulted: a proposal is what the review card renders, and the whole
        # reason it carries a label is that a missing one printed the slug.
        role_label=role_id.replace("-", " ").title(),
        division_ocdid=division_ocdid,
        headcount=len(person_ids),
        members=[
            DerivedMembership(person_id=person_id, membership_label=label) for person_id in person_ids
        ],
    )


def _held(
    person_id,
    role_id,
    division_ocdid,
    post_id="post-1",
    meta_is_tracked=True,
    role_label="",
    organization_id=_COUNCIL,
):
    return ExistingMembership(
        id=f"membership-{person_id}",
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:zz/place:testville/government",
        person_id=person_id,
        organization_id=organization_id,
        post=MembershipPost(
            id=post_id,
            role_id=role_id,
            role_label=role_label,
            division_ocdid=division_ocdid,
            label=derive_post_label(role_label, division_ocdid),
            meta_is_tracked=meta_is_tracked,
        ),
    )


@pytest.mark.unit
def test_the_same_post_is_not_a_review_item():
    """The majority case, and the whole reason this is a diff. A roster restating what we
    already hold asks nobody for anything."""
    changes = _propose([_post("mayor", _BASE, "a")], [_held("a", "mayor", _BASE)])

    assert [c.disposition for c in changes] == [MembershipDisposition.UNCHANGED]
    assert surfaces_for_review(changes[0]) is False


@pytest.mark.unit
def test_somebody_we_hold_nothing_for_is_new():
    changes = _propose([_post("mayor", _BASE, "a")], [])

    assert changes[0].disposition is MembershipDisposition.NEW
    assert changes[0].from_post is None
    assert surfaces_for_review(changes[0]) is True


@pytest.mark.unit
def test_a_different_post_is_a_move_and_says_where_from():
    """Both ends matter: a review row reading "now Mayor" without "was Ward 3" cannot be
    judged."""
    changes = _propose(
        [_post("mayor", _BASE, "a")],
        [_held("a", "council-member", _WARD_3, post_id="old-post")],
    )

    assert changes[0].disposition is MembershipDisposition.MOVED
    assert changes[0].from_post is not None
    assert changes[0].from_post.id == "old-post"


@pytest.mark.unit
def test_a_holder_the_scrape_did_not_name_is_absent():
    """Sourced from what we hold, not from the scrape — there is no incoming row to hang a
    disappearance on, so walking the derivation alone can never find one."""
    changes = _propose(
        [_post("mayor", _BASE, "a")], [_held("b", "council-member", _WARD_3)]
    )

    absent = [c for c in changes if c.disposition is MembershipDisposition.ABSENT]
    assert [c.person_id for c in absent] == ["b"]
    assert surfaces_for_review(absent[0]) is True


@pytest.mark.unit
def test_an_absence_names_the_post_it_left():
    """The label is derived, but from the role we held them in — not from the incoming post.
    Deriving without it produced "Ward 3" for a ward and an empty string at-large, which reads
    as though they held nothing."""
    changes = _propose(
        [_post("mayor", _BASE, "a")],
        [_held("b", "council-member", _WARD_3, role_label="Council Member")],
    )

    absent = next(c for c in changes if c.disposition is MembershipDisposition.ABSENT)
    assert absent.post.label == "Council Member, Ward 3"


@pytest.mark.unit
def test_every_absence_surfaces_while_tracked_is_undecided():
    """`meta_is_tracked` rides along on the change and is deliberately not read. Skipping review
    on a flag whose meaning is unsettled is the expensive way to discover it was wrong; the
    absence is closed either way, at ingest."""
    changes = _propose(
        [_post("mayor", _BASE, "a")],
        [_held("b", "city-attorney", _BASE, meta_is_tracked=False)],
    )

    absent = next(c for c in changes if c.disposition is MembershipDisposition.ABSENT)
    assert absent.post.meta_is_tracked is False
    assert surfaces_for_review(absent) is True


@pytest.mark.unit
def test_an_empty_scrape_proposes_nothing():
    """The guard `close_absent` already makes: an empty roster is a failed scrape, not a
    dissolved council, and without this every holder becomes a false departure."""
    changes = _propose([], [_held("a", "mayor", _BASE)])

    assert changes == []


@pytest.mark.unit
def test_a_body_the_scrape_never_read_proposes_nothing():
    """The bound publish already closes within: a council-only scrape says nothing about a school
    board member. Without it, review shows a departure publish will refuse to make."""
    changes = _propose(
        [_post("mayor", _BASE, "a")],
        [_held("b", "trustee", _BASE, organization_id=_MAYORS_OFFICE)],
        organizations_read=(_COUNCIL,),
    )

    assert [change.person_id for change in changes] == ["a"]


@pytest.mark.unit
def test_a_body_read_that_returned_nobody_still_proposes_the_absence():
    """Read and empty is not the same as never looked at. The scrape covered the mayor's office
    and did not find them there, which is exactly the departure a reviewer should see."""
    changes = _propose(
        [_post("council-member", _BASE, "a")],
        [_held("b", "mayor", _BASE, organization_id=_MAYORS_OFFICE)],
    )

    absent = next(change for change in changes if change.person_id == "b")
    assert absent.disposition is MembershipDisposition.ABSENT


@pytest.mark.unit
def test_the_proposed_label_rides_along():
    changes = _propose(
        [_post("mayor", _BASE, "a", label="Commissioner Of Public Safety")], []
    )

    assert changes[0].membership_label == "Commissioner Of Public Safety"


# `still_held` and `still_listed` were deleted with the ingest-time observation writes they
# fed. Both answered "who should stay open" for `advance_last_seen_at` and `close_absent`,
# which now run only at publish — where `close_absent` takes `incoming_ids`, everyone in the
# published roster, a more direct answer than a disposition filter.




@pytest.mark.unit
def test_an_all_unchanged_roster_asks_nobody_anything():
    changes = _propose([_post("mayor", _BASE, "a")], [_held("a", "mayor", _BASE)])

    assert nothing_to_review(changes) is True


@pytest.mark.unit
def test_one_review_item_is_enough_to_keep_the_scrape():
    changes = _propose(
        [_post("mayor", _BASE, "a"), _post("council-member", _WARD_3, "b")],
        [_held("a", "mayor", _BASE)],
    )

    assert nothing_to_review(changes) is False


@pytest.mark.unit
def test_an_empty_proposal_is_a_failed_scrape_not_a_quiet_one():
    """A scrape that agrees with us proposes all-`unchanged`; one that found nothing proposes
    nothing at all. Dismissing the second would retire a failure as though it were agreement."""
    assert nothing_to_review([]) is False


# --- per organization ------------------------------------------------------------------------


def _dispositions(changes):
    return sorted((c.organization_id, c.post.role_id, c.disposition) for c in changes)


@pytest.mark.unit
def test_a_person_in_two_bodies_restated_by_the_scrape_is_unchanged_in_both():
    """Compared per person, the mayor's office post read as a move away from the council one."""
    changes = _propose(
        [
            _post("council-member", _WARD_3, "a", organization_id=_COUNCIL),
            _post("mayor", _BASE, "a", organization_id=_MAYORS_OFFICE),
        ],
        [
            _held("a", "council-member", _WARD_3, organization_id=_COUNCIL),
            _held("a", "mayor", _BASE, post_id="post-2", organization_id=_MAYORS_OFFICE),
        ],
    )

    assert _dispositions(changes) == [
        (_COUNCIL, "council-member", MembershipDisposition.UNCHANGED),
        (_MAYORS_OFFICE, "mayor", MembershipDisposition.UNCHANGED),
    ]


@pytest.mark.unit
def test_a_move_in_one_body_names_where_from_in_that_body_only():
    changes = _propose(
        [
            _post("council-member", _BASE, "a", organization_id=_COUNCIL),
            _post("mayor", _BASE, "a", organization_id=_MAYORS_OFFICE),
        ],
        [
            _held("a", "council-member", _WARD_3, organization_id=_COUNCIL),
            _held("a", "mayor", _BASE, post_id="post-2", organization_id=_MAYORS_OFFICE),
        ],
    )

    [moved] = [c for c in changes if c.disposition is MembershipDisposition.MOVED]
    assert moved.from_post is not None
    assert (moved.organization_id, moved.from_post.id) == (_COUNCIL, "post-1")


@pytest.mark.unit
def test_a_post_in_a_body_the_person_holds_nothing_in_is_new():
    changes = _propose(
        [_post("mayor", _BASE, "a", organization_id=_MAYORS_OFFICE)],
        [_held("a", "council-member", _WARD_3, organization_id=_COUNCIL)],
    )

    assert _dispositions(changes) == [(_MAYORS_OFFICE, "mayor", MembershipDisposition.NEW)]
