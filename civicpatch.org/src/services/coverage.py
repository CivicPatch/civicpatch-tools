import database.issues as issues_db
import database.jurisdictions as jurisdictions_db
import database.pipeline_runs as pipeline_runs_db
import database.pull_requests as pull_requests_db
from core.coverage import StateCoverage, summarize_state_coverage


async def get_state_coverage(state: str) -> StateCoverage:
    sets = await jurisdictions_db.get_state_jurisdiction_sets(state)
    to_review = await pull_requests_db.get_open_pr_ocdids_by_state(state)
    scraping = await pipeline_runs_db.get_active_pipeline_run_jurisdiction_ocdids()
    blocked = await issues_db.get_pending_issue_ocdids()
    return summarize_state_coverage(
        total=sets.total,
        scrapeable=sets.scrapeable,
        covered_fresh=sets.covered_fresh,
        covered_stale=sets.covered_stale,
        blocked=blocked,
        to_review=to_review,
        scraping=scraping,
    )
