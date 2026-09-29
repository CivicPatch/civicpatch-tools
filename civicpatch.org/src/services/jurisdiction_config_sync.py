import database.jurisdiction_configs as jurisdiction_configs_db
import lib.github.api as github_service
import yaml
from schemas.jurisdiction_configs import JurisdictionConfigSyncRequest, JurisdictionConfigVersion
from shared.utils.layered_config import ConfigFile


def parse_jurisdiction_config(raw: str) -> ConfigFile:
    return ConfigFile.model_validate(yaml.safe_load(raw) or {})


async def sync_jurisdiction_configs(request: JurisdictionConfigSyncRequest) -> None:
    """Read each merged config file at its commit and apply it."""
    for path in request.paths:
        raw = await github_service.get_github_file_contents(path, ref=request.commit_sha)
        if raw is None:
            raise RuntimeError(f"sync_jurisdiction_configs: could not read {path} at {request.commit_sha}")
        config = parse_jurisdiction_config(raw)
        version = JurisdictionConfigVersion(
            path=path, commit_sha=request.commit_sha, pull_request_number=request.pull_request_number
        )
        await jurisdiction_configs_db.sync_jurisdiction_config(version, config)
