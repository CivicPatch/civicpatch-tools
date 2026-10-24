import pytest

from database.review_priority import _ISSUE_WEIGHT, issue_count, issue_priority
from shared.utils.statuses import PipelineIssueType


@pytest.mark.unit
def test_every_stored_issue_type_is_weighted():
    """An unweighted type silently scores 1. Nothing else notices, so the next person to add a
    type finds out from a misranked queue."""
    assert set(_ISSUE_WEIGHT) == set(PipelineIssueType)


@pytest.mark.unit
def test_the_score_and_the_count_read_the_runs_pending_issues():
    """Asserted on the SQL text because the alternative is noticing in prod."""
    for sql in (issue_count("c.id"), issue_priority("c.id")):
        assert "FROM pipeline_run_issues" in sql
        assert "'pending'" in sql
