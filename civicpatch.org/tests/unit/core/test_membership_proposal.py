import pytest

from core.membership_proposal import (
    Disposition,
    ExistingMembership,
    nothing_to_review,
    propose,
    still_held,
    still_listed,
    surfaces_for_review,
)
from core.post_derivation import DerivedMember, DerivedPost

# Pure — a scrape's derivation and what we already hold, in; the difference, out. No taxonomy
# and no database, because the diff is only about which seat a person is on.

_BASE = "ocd-division/country:us/state:zz/place:testville"
_WARD_3 = f"{_BASE}/ward:3"


def _post(role_id, division_ocdid, *person_ids, label=None):
    return DerivedPost(
        role_id=role_id,
        # Required, not defaulted: a proposal is what the review card renders, and the whole
        # reason it carries a label is that a missing one printed the slug.
        role_label=role_id.replace("-", " ").title(),
        division_ocdid=division_ocdid,
        headcount=len(person_ids),
        members=[
            DerivedMember(person_id=person_id, label=label) for person_id in person_ids
        ],
    )


def _held(
    person_id,
    role_id,
    division_ocdid,
    post_id="post-1",
    is_tracked=True,
    role_label="",
    post_label=None,
):
    return ExistingMembership(
        person_id=person_id,
        post_id=post_id,
        role_id=role_id,
        role_label=role_label,
        division_ocdid=division_ocdid,
        post_label=post_label,
        is_tracked=is_tracked,
    )


@pytest.mark.unit
def test_the_same_seat_is_not_a_review_item():
    """The majority case, and the whole reason this is a diff. A roster restating what we
    already hold asks nobody for anything."""
    changes = propose([_post("mayor", _BASE, "a")], [_held("a", "mayor", _BASE)])

    assert [c.disposition for c in changes] == [Disposition.UNCHANGED]
    assert surfaces_for_review(changes[0]) is False


@pytest.mark.unit
def test_somebody_we_hold_nothing_for_is_new():
    changes = propose([_post("mayor", _BASE, "a")], [])

    assert changes[0].disposition is Disposition.NEW
    assert changes[0].from_post_id is None
    assert surfaces_for_review(changes[0]) is True


@pytest.mark.unit
def test_a_different_seat_is_a_move_and_says_where_from():
    """Both ends matter: a review row reading "now Mayor" without "was Ward 3" cannot be
    judged."""
    changes = propose(
        [_post("mayor", _BASE, "a")],
        [_held("a", "council-member", _WARD_3, post_id="old-post")],
    )

    assert changes[0].disposition is Disposition.MOVED
    assert changes[0].from_post_id == "old-post"


@pytest.mark.unit
def test_a_holder_the_scrape_did_not_name_is_absent():
    """Sourced from what we hold, not from the scrape — there is no incoming row to hang a
    disappearance on, so walking the derivation alone can never find one."""
    changes = propose(
        [_post("mayor", _BASE, "a")], [_held("b", "council-member", _WARD_3)]
    )

    absent = [c for c in changes if c.disposition is Disposition.ABSENT]
    assert [c.person_id for c in absent] == ["b"]
    assert surfaces_for_review(absent[0]) is True


@pytest.mark.unit
def test_an_absence_is_named_by_the_post_it_left():
    """An absence is the one change whose post exists, so its own name wins — a derived label
    would overwrite whatever a human chose to call the seat."""
    changes = propose(
        [_post("mayor", _BASE, "a")],
        [
            _held(
                "b",
                "council-member",
                _WARD_3,
                role_label="Council Member",
                post_label="Council Member and Deputy Mayor",
            )
        ],
    )

    absent = next(c for c in changes if c.disposition is Disposition.ABSENT)
    assert absent.post_label == "Council Member and Deputy Mayor"


@pytest.mark.unit
def test_an_absence_from_an_unnamed_post_still_names_its_role():
    """Nobody named the post, so the label is derived — but from the role we held them in.
    Deriving without it produced "Ward 3" for a ward and an empty string at-large, which reads
    as though they held nothing."""
    changes = propose(
        [_post("mayor", _BASE, "a")],
        [_held("b", "council-member", _WARD_3, role_label="Council Member")],
    )

    absent = next(c for c in changes if c.disposition is Disposition.ABSENT)
    assert absent.post_label == "Council Member, Ward 3"


@pytest.mark.unit
def test_every_absence_surfaces_while_tracked_is_undecided():
    """`is_tracked` rides along on the change and is deliberately not read. Skipping review on
    a flag whose meaning is unsettled is the expensive way to discover it was wrong; the
    absence is closed either way, at ingest."""
    changes = propose(
        [_post("mayor", _BASE, "a")],
        [_held("b", "city-attorney", _BASE, is_tracked=False)],
    )

    absent = next(c for c in changes if c.disposition is Disposition.ABSENT)
    assert absent.is_tracked is False
    assert surfaces_for_review(absent) is True


@pytest.mark.unit
def test_an_empty_scrape_proposes_nothing():
    """The guard `close_absent` already makes: an empty roster is a failed scrape, not a
    dissolved council, and without this every holder becomes a false departure."""
    changes = propose([], [_held("a", "mayor", _BASE)])

    assert changes == []


@pytest.mark.unit
def test_the_proposed_label_rides_along():
    changes = propose(
        [_post("mayor", _BASE, "a", label="Commissioner Of Public Safety")], []
    )

    assert changes[0].label == "Commissioner Of Public Safety"


@pytest.mark.unit
def test_only_the_unchanged_are_still_held():
    """Advancing `last_seen_at` on a mover would assert the seat they left."""
    changes = propose(
        [_post("mayor", _BASE, "a"), _post("council-member", _WARD_3, "b")],
        [_held("a", "mayor", _BASE), _held("b", "city-attorney", _BASE)],
    )

    assert still_held(changes) == ["a"]


@pytest.mark.unit
def test_a_mover_is_still_listed():
    """A move is still a sighting. Closing someone because the scrape named them somewhere
    else would record a departure that did not happen."""
    changes = propose(
        [_post("mayor", _BASE, "a"), _post("council-member", _WARD_3, "b")],
        [
            _held("a", "mayor", _BASE),
            _held("b", "city-attorney", _BASE),
            _held("c", "clerk", _BASE),
        ],
    )

    assert sorted(still_listed(changes)) == ["a", "b"]


@pytest.mark.unit
def test_an_all_unchanged_roster_asks_nobody_anything():
    changes = propose([_post("mayor", _BASE, "a")], [_held("a", "mayor", _BASE)])

    assert nothing_to_review(changes) is True


@pytest.mark.unit
def test_one_review_item_is_enough_to_keep_the_scrape():
    changes = propose(
        [_post("mayor", _BASE, "a"), _post("council-member", _WARD_3, "b")],
        [_held("a", "mayor", _BASE)],
    )

    assert nothing_to_review(changes) is False


@pytest.mark.unit
def test_an_empty_proposal_is_a_failed_scrape_not_a_quiet_one():
    """A scrape that agrees with us proposes all-`unchanged`; one that found nothing proposes
    nothing at all. Dismissing the second would retire a failure as though it were agreement."""
    assert nothing_to_review([]) is False
