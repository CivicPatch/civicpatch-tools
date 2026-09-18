import pytest

from core.changeset_lifecycle import REVIEW_POOL_KINDS
from database.changeset_predicates import REVIEW_POOL_KIND_VALUES_SQL


@pytest.mark.unit
def test_review_pool_kinds_match_the_lifecycle():
    spelled_out = set()
    for value in REVIEW_POOL_KIND_VALUES_SQL.split(","):
        spelled_out.add(value.strip().strip("'"))

    assert spelled_out == {kind.value for kind in REVIEW_POOL_KINDS}
