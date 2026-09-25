"""`claims_from_posts`: the posts a person should hold, as claims.

The edit route (step 9) sends the whole set rather than a delta, so the server never has to be
told which way a move went. Pure — no roster, no database.
"""

import pytest

from core.people_edits import POSTS_FIELD, claims_from_posts
from schemas.claims import ClaimKind, DefaultNote, EntityType

MAYOR = "11111111-1111-5111-8111-111111111111"
CLERK = "22222222-2222-5222-8222-222222222222"


def _pairs(claims):
    return [(claim.kind, claim.value) for claim in claims]


@pytest.mark.unit
def test_an_unchanged_set_files_nothing():
    """The editor sends every person, so most calls say the same thing twice. Saying it again
    must not fill the audit trail with claims nobody made."""
    assert claims_from_posts("p1", [MAYOR], [MAYOR]) == []


@pytest.mark.unit
def test_a_new_post_is_an_accept():
    claims = claims_from_posts("p1", [], [MAYOR])

    assert _pairs(claims) == [(ClaimKind.ACCEPT, MAYOR)]
    assert claims[0].entity_type is EntityType.PERSON
    assert claims[0].entity_id == "p1"
    assert claims[0].field_path == POSTS_FIELD


@pytest.mark.unit
def test_a_dropped_post_is_a_reject():
    assert _pairs(claims_from_posts("p1", [MAYOR], [])) == [
        (ClaimKind.REJECT, MAYOR)
    ]


@pytest.mark.unit
def test_a_move_is_both_halves():
    """One id arrives, another leaves. The fold's collapse decides which survives, so the
    route never has to name the move."""
    assert _pairs(claims_from_posts("p1", [MAYOR], [CLERK])) == [
        (ClaimKind.ACCEPT, CLERK),
        (ClaimKind.REJECT, MAYOR),
    ]


@pytest.mark.unit
def test_removing_a_person_rejects_every_post_they_hold():
    """"Remove person" is `posts: []` — the same claim per post, not a special act."""
    assert _pairs(claims_from_posts("p1", [CLERK, MAYOR], [])) == [
        (ClaimKind.REJECT, MAYOR),
        (ClaimKind.REJECT, CLERK),
    ]


@pytest.mark.unit
def test_the_claims_do_not_depend_on_the_order_they_were_given():
    """R6: two identical edits file identical claims, whatever order the client listed them."""
    forwards = claims_from_posts("p1", [MAYOR, CLERK], [CLERK])
    backwards = claims_from_posts("p1", [CLERK, MAYOR], [CLERK])

    assert _pairs(forwards) == _pairs(backwards)


@pytest.mark.unit
def test_every_claim_carries_a_source():
    """§5: a claim nobody can trace is the thing `sources` exists to prevent. An edit has no
    url of its own, so the note says what act it was."""
    claims = claims_from_posts("p1", [MAYOR], [CLERK], changeset_id="c1")

    assert all(claim.sources == [claims[0].sources[0]] for claim in claims)
    assert claims[0].sources[0].note == DefaultNote.EDITED
    assert all(claim.changeset_id == "c1" for claim in claims)
