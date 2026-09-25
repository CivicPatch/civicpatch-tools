"""`POST_IS_VERIFIED` names the same fields `_accept_fields` writes.

The predicate is a `LiteralString` spliced into several queries, so its field list cannot be
joined from `_HUMAN_FIELDS` at runtime and is spelled out instead. This is what stops the two
drifting: add a human field and the predicate would silently ignore posts verified through it.

Same shape as `test_check_constraints_match_enums.py` -- a duplicated vocabulary, pinned rather
than deduplicated, because the duplication buys something (here, SQL injection safety).
"""

import pytest

from database.posts import _HUMAN_FIELDS, POST_IS_VERIFIED, POST_LABEL_FIELD


@pytest.mark.unit
def test_the_verified_arm_names_the_human_fields():
    for field in _HUMAN_FIELDS:
        assert f"'{field}'" in POST_IS_VERIFIED


@pytest.mark.unit
def test_naming_a_post_does_not_vouch_for_it():
    """A `label` claim is a rename, not a human saying the post exists.

    It counted until 2026-09-24, from when a post claim meant a vouch -- a reading §17 retired on
    2026-09-18. Renaming a post through `set_post_label` marked it verified and took it out of
    the review queue.
    """
    assert f"'{POST_LABEL_FIELD}'" not in POST_IS_VERIFIED
