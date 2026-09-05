import asyncio

import database.coverage as coverage_db
import database.issues as issues_db
import database.jurisdictions as jurisdictions_db
import database.pipeline_runs as pipeline_runs_db
import database.review_pool as review_pool_db
from core.coverage import StateCoverage, summarize_state_coverage


async def get_state_coverage(state: str) -> StateCoverage:
    sets, to_review, scraping, blocked = await asyncio.gather(
        jurisdictions_db.get_state_jurisdiction_sets(state),
        review_pool_db.jurisdiction_ocdids_with_open_changesets(state),
        pipeline_runs_db.jurisdiction_ocdids_with_unfinished_runs_in_state(state),
        issues_db.jurisdiction_ocdids_with_pending_issues_in_state(state),
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
    (database.coverage) with `needs_review`, sourced from open PRs (database.review_pool) —
    the same to_review signal get_state_coverage above already uses for its bucket count.
    """
    rows = await coverage_db.get_municipality_rows_for_state(state)
    open_pr_ocdids = await review_pool_db.jurisdiction_ocdids_with_open_changesets(state)
    return [
        {**row, "needs_review": row["jurisdiction_ocdid"] in open_pr_ocdids}
        for row in rows
    ]
