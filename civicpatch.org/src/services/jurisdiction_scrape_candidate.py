import database.issues as issues_db
import database.jurisdictions as jurisdictions_db
import database.pipeline_runs as pipeline_runs_db
import database.review_pool as review_pool_db
from schemas.common import Jurisdiction


async def get_scrape_candidates(state: str, num_jurisdictions: int) -> list[Jurisdiction]:
    candidates = await jurisdictions_db.get_stale_jurisdictions(state)
    open_pr_ocdids = await review_pool_db.open_ocdids_by_state(state)
    active_job_ocdids = await pipeline_runs_db.get_active_pipeline_run_jurisdiction_ocdids()
    pending_issue_ocdids = await issues_db.get_pending_issue_ocdids()

    excluded = open_pr_ocdids | active_job_ocdids | pending_issue_ocdids
    eligible = [j for j in candidates if j.id not in excluded]
    return eligible[:num_jurisdictions]
