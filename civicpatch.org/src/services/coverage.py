import asyncio

import database.coverage as coverage_db
import database.issues as issues_db
import database.jurisdictions as jurisdictions_db
import database.pipeline_runs as pipeline_runs_db
import database.pull_requests as pull_requests_db
from core.coverage import StateCoverage, summarize_state_coverage


async def get_state_coverage(state: str) -> StateCoverage:
    sets, to_review, scraping, blocked = await asyncio.gather(
        jurisdictions_db.get_state_jurisdiction_sets(state),
        pull_requests_db.get_open_pr_ocdids_by_state(state),
        pipeline_runs_db.get_active_pipeline_run_jurisdiction_ocdids_by_state(state),
        issues_db.get_pending_issue_ocdids_by_state(state),
    )
    return summarize_state_coverage(
        total=sets.total,
        scrapeable=sets.scrapeable,
        covered_fresh=sets.covered_fresh,
        covered_stale=sets.covered_stale,
        blocked=blocked,
        to_review=to_review,
        scraping=scraping,
    )


async def get_municipality_list(state: str) -> list[dict]:
    """Municipality list for the browsable page (§8) — combines per-jurisdiction map status
    (database.coverage) with `needs_review`, sourced from open PRs (database.pull_requests) —
    the same to_review signal get_state_coverage above already uses for its bucket count.
    """
    rows = await coverage_db.get_municipality_rows_for_state(state)
    open_pr_ocdids = await pull_requests_db.get_open_pr_ocdids_by_state(state)
    return [
        {**row, "needs_review": row["jurisdiction_ocdid"] in open_pr_ocdids}
        for row in rows
    ]
