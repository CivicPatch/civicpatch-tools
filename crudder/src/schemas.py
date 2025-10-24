from pydantic import BaseModel, model_validator

class PullRequest(BaseModel):
    branch_name: str
    jurisdiction_id: str = ""

    @model_validator(mode="after")
    def set_jurisdiction_id(self):
        if not self.jurisdiction_id and self.branch_name:
            self.jurisdiction_id = git_branch_to_jurisdiction_id(self.branch_name)
        return self

class Jurisdiction(BaseModel):
    id: str
    name: str
    url: str | None

def git_branch_to_jurisdiction_id(branch: str) -> str:
    """
    Converts a git branch name back to a jurisdiction ID.
    Example:
      "2025-09-25-1a2b-state-wa-place-seattle-government"
      -> "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
      "2025-09-25-1a2b-state-il-county-dupage-place-naperville-government"
      -> "ocd-jurisdiction/country:us/state:il/county:dupage/place:naperville/government"
    """
    # Remove request_id prefix
    parts = branch.split('-', 3)
    if len(parts) < 4:
        raise ValueError(f"Branch name format invalid: {branch}")
    rest = parts[3]  # e.g. "state-wa-place-seattle-government"
    tokens = rest.split('-')
    idx = 0
    result = ["ocd-jurisdiction/country:us"]
    while idx < len(tokens):
        if tokens[idx] == "state":
            result.append(f"state:{tokens[idx+1]}")
            idx += 2
        elif tokens[idx] == "county":
            result.append(f"county:{tokens[idx+1]}")
            idx += 2
        elif tokens[idx] == "place":
            result.append(f"place:{tokens[idx+1]}")
            idx += 2
        else:
            idx += 1  # skip unknown tokens
    # Add the last token (e.g. "government") if present and not already included
    if tokens and tokens[-1] not in {"state", "county", "place"}:
        result.append(tokens[-1])
    return "/".join(result)
