import pytest

from database.review_queue import _ISSUE_WEIGHT, issue_count, issue_priority
from shared.schemas import IssueCode


@pytest.mark.unit
def test_every_issue_code_is_weighted():
    """An unweighted code silently scores 1 — the flat ordering this table replaced. Nothing
    else notices, so the next person to add a code finds out from a misranked queue."""
    assert set(_ISSUE_WEIGHT) == set(IssueCode)


@pytest.mark.unit
def test_the_score_and_the_count_read_the_same_two_sources():
    """The badge and the card must agree, and they only do while both read stored issues and
    unverified posts. Asserted on the SQL text because the alternative is noticing in prod."""
    for sql in (issue_count("r.review_json", "r.j"), issue_priority("r.review_json", "r.j")):
        assert "r.review_json" in sql
        assert "FROM posts" in sql
