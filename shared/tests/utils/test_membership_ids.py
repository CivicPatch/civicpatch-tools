import uuid

from shared.utils.membership_ids import membership_id

_PERSON = "11111111-1111-1111-1111-111111111111"
_POST = "council:mayor"


def test_the_same_pair_always_gets_the_same_id():
    assert membership_id(_PERSON, _POST) == membership_id(_PERSON, _POST)


def test_the_id_is_a_uuid():
    """`assertions.entity_id` is a uuid column, which is why a readable composite key is not
    available and the fold has to recompute this hash to find a claim's post."""
    assert uuid.UUID(membership_id(_PERSON, _POST))


def test_a_different_person_gets_a_different_id():
    other = "22222222-2222-2222-2222-222222222222"

    assert membership_id(other, _POST) != membership_id(_PERSON, _POST)


def test_a_different_post_gets_a_different_id():
    assert membership_id(_PERSON, "council:member") != membership_id(_PERSON, _POST)


def test_the_id_never_changes():
    """Every membership claim ever filed is addressed by this value. Changing the namespace or
    the encoding orphans all of them silently, so pin it."""
    assert membership_id(_PERSON, _POST) == "95253511-3f02-5d63-838e-081ac3c3e2fc"
