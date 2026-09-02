import pytest

from database.review_priority import _ISSUE_WEIGHT, issue_count, issue_priority
from shared.schemas import IssueCode


@pytest.mark.unit
def test_every_issue_code_is_weighted():
    """An unweighted code silently scores 1 — the flat ordering this table replaced. Nothing
    else notices, so the next person to add a code finds out from a misranked queue."""
    assert set(_ISSUE_WEIGHT) == set(IssueCode)


@pytest.mark.unit
def test_the_score_and_the_count_read_the_same_source():
    """Both read unverified posts and nothing else. The five roster checks are computed at
    read from two rosters SQL cannot derive, so they show on the card but cannot sort the pool
    — see the module note. Asserted on the SQL text because the alternative is noticing in
    prod."""
    for sql in (issue_count("r.j"), issue_priority("r.j")):
        assert "FROM posts" in sql
        assert "review_json" not in sql
