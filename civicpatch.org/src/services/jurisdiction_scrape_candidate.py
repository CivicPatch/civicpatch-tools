import shared.utils.id_utils
import database.issues as issues_db
import database.jurisdictions as jurisdictions_db
import database.pipeline_runs as pipeline_runs_db
import database.review_pool as review_pool_db
from schemas.common import Jurisdiction


async def get_scrape_candidates(
    state: str, num_jurisdictions: int | None = None
) -> list[Jurisdiction]:
    """Every jurisdiction due a scrape, or the first `num_jurisdictions` of them.

    "Eligible" already bounds this: stale past the freshness window, active, has a url, and not
    blocked by an open review, a running scrape or a pending issue.
    """
    candidates = await jurisdictions_db.get_stale_jurisdictions(state)
    open_pr_ocdids = await review_pool_db.open_ocdids_by_state(state)
    active_job_ocdids = await pipeline_runs_db.get_active_pipeline_run_jurisdiction_ocdids()
    pending_issue_ocdids = await issues_db.get_pending_issue_ocdids()

    excluded = open_pr_ocdids | active_job_ocdids | pending_issue_ocdids
    eligible = [j for j in candidates if j.id not in excluded]
    return eligible[:num_jurisdictions] if num_jurisdictions else eligible


async def claim_scrape_candidates(
    state: str, num_jurisdictions: int | None = None, created_by_user_id: str | None = None
) -> list[dict]:
    """Pick this state's next candidates and start a run for each.

    A run, not a changeset: a changeset is a proposal, and nothing has been proposed until the
    scrape comes back with a roster. `people_collector` mints one at ingest if it does.

    One call because the two halves must not be separated: starting the run is what takes a
    jurisdiction out of the candidate pool, so a caller that selected and then started in two
    steps could hand the same place to two batches.

    Safe to retry. `get_scrape_candidates` excludes jurisdictions with a non-terminal run, so a
    second call after a partial failure picks up where the first left off rather than
    double-registering.
    """
    candidates = await get_scrape_candidates(state, num_jurisdictions)
    items = []
    for candidate in candidates:
        run_id = shared.utils.id_utils.make_changeset_id()
        await pipeline_runs_db.register_run(
            run_id=run_id,
            jurisdiction_ocdid=candidate.id,
            arguments_json={
                "jurisdiction_ocdid": candidate.id,
                "name": candidate.name,
                "url": candidate.url,
                "source_urls": None,
            },
            created_by_user_id=created_by_user_id,
        )
        items.append(
            {
                "jurisdiction_ocdid": candidate.id,
                "changeset_id": run_id,
                "name": candidate.name,
                "url": candidate.url,
            }
        )
    return items
