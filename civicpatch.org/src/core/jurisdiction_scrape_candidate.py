import yaml

import database.pipeline_issues as pipeline_issues_db
import database.pipeline_runs as database
import database.pull_requests as pull_requests_db
import lib.github.api as github_api_service
from schemas.common import Jurisdiction


async def get_scrape_candidates(state: str, num_jurisdictions: int) -> list[Jurisdiction]:
    jurisdictions_content = await github_api_service.get_github_file_contents(f"data_source/{state}/local/jurisdictions.yml")
    metadata_content = await github_api_service.get_github_file_contents(f"data_source/{state}/local/jurisdictions_metadata.yml")
    if jurisdictions_content is None:
        raise ValueError(f"Could not find jurisdictions file for state {state!r}")

    entries = yaml.safe_load(jurisdictions_content).get("jurisdictions", [])
    metadata_by_id = yaml.safe_load(metadata_content).get("jurisdictions_by_id", {}) if metadata_content else {}
    open_pr_ocdids = await pull_requests_db.get_open_pr_ocdids_by_state(state)
    active_job_ocdids = await database.get_active_pipeline_run_jurisdiction_ocdids()
    pending_error_ocdids = await pipeline_issues_db.get_pending_error_issue_ocdids()

    def is_eligible(entry: dict) -> bool:
        ocdid = entry.get("id")
        return bool(
            ocdid
            and entry.get("url")
            and ocdid not in open_pr_ocdids
            and ocdid not in active_job_ocdids
            and ocdid not in pending_error_ocdids
        )

    def to_jurisdiction(entry: dict) -> Jurisdiction:
        return Jurisdiction(id=entry["id"], name=entry["name"], url=entry["url"])

    # Entries absent from metadata, or present but without updated_at, have never been scraped
    never_updated = [
        to_jurisdiction(e)
        for e in entries
        if is_eligible(e) and not metadata_by_id.get(e["id"], {}).get("updated_at")
    ]
    if len(never_updated) >= num_jurisdictions:
        return never_updated[:num_jurisdictions]

    already_added = {j.id for j in never_updated}
    older_eligible = sorted(
        (metadata_by_id.get(e["id"], {}).get("updated_at") or "", e["id"])
        for e in entries
        if is_eligible(e) and e["id"] not in already_added
    )
    result = list(never_updated)
    for _, ocdid in older_eligible:
        if len(result) >= num_jurisdictions:
            break
        entry = next(e for e in entries if e["id"] == ocdid)
        result.append(to_jurisdiction(entry))

    return result
