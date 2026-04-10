import yaml

import services.github.github_api_service as github_api_service
from schemas.common import Jurisdiction


async def get_scrape_candidates(state: str, num_jurisdictions: int) -> list[Jurisdiction]:
    jurisdictions_content = await github_api_service.get_github_file_contents(f"data_source/{state}/jurisdictions.yml")
    metadata_content = await github_api_service.get_github_file_contents(f"data_source/{state}/jurisdictions_metadata.yml")
    if jurisdictions_content is None:
        raise ValueError(f"Could not find jurisdictions file for state {state!r}")
    if metadata_content is None:
        raise ValueError(f"Could not find jurisdictions metadata file for state {state!r}")

    entries = yaml.safe_load(jurisdictions_content).get("jurisdictions", [])
    metadata_by_id = yaml.safe_load(metadata_content).get("jurisdictions_by_id", {})
    open_pr_ocdids = {pr.jurisdiction_ocdid for pr in await github_api_service.get_open_pull_requests(state_code=state)}

    def is_eligible(ocdid: str) -> bool:
        if ocdid in open_pr_ocdids:
            return False
        entry = next((e for e in entries if e.get("id") == ocdid), None)
        return bool(entry and entry.get("url"))

    def to_jurisdiction(ocdid: str) -> Jurisdiction:
        entry = next(e for e in entries if e.get("id") == ocdid)
        return Jurisdiction(id=entry["id"], name=entry["name"], url=entry["url"])

    never_updated = [
        to_jurisdiction(ocdid)
        for ocdid, meta in metadata_by_id.items()
        if not meta.get("updated_at") and is_eligible(ocdid)
    ]
    if len(never_updated) >= num_jurisdictions:
        return never_updated[:num_jurisdictions]

    already_added = {j.id for j in never_updated}
    older_eligible = sorted(
        (meta.get("updated_at") or "", ocdid)
        for ocdid, meta in metadata_by_id.items()
        if is_eligible(ocdid) and ocdid not in already_added
    )
    for _, ocdid in older_eligible:
        if len(never_updated) >= num_jurisdictions:
            break
        never_updated.append(to_jurisdiction(ocdid))

    return never_updated
