from pydantic import BaseModel


class JurisdictionConfigSyncRequest(BaseModel):
    """Sent by open-data's merge job once a config PR merges."""

    commit_sha: str
    pull_request_number: int | None = None
    paths: list[str]


class JurisdictionConfigVersion(BaseModel):
    """Where a synced file came from, recorded on every activity row it writes."""

    path: str
    commit_sha: str
    pull_request_number: int | None
