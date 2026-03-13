from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import shared.utils.id_utils as id_utils
from pydantic import BaseModel

KNOWN_PLACE_KEYS = ["place", "special_district"]


class RouteCategory(str, Enum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    TEAM_REQUIRED = "team_required"
    SERVICE = "service"


class Role(str, Enum):
    DEFAULT = "default"
    CONTRIBUTORS = "contributors"
    MAINTAINERS = "maintainers"
    ADMINS = "admins"


class PullRequest(BaseModel):
    branch_name: str
    jurisdiction_ocdid: str = ""
    request_id: str = ""
    url: str
    pull_request_number: str = ""

    def model_post_init(self, __context):
        try:
            if not self.jurisdiction_ocdid and self.branch_name:
                parts = id_utils.git_branch_to_parts(self.branch_name)
                self.jurisdiction_ocdid = parts.get("jurisdiction_ocdid", "")
                self.request_id = parts.get("request_id", "")
            if self.url:
                self.pull_request_number = self.url.split("/")[-1]
        except Exception as e:
            print(
                f"git branch does not match jurisdiction id format: {self.branch_name}. Error: {e}"
            )
            self.jurisdiction_ocdid = ""


class Jurisdiction(BaseModel):
    id: str
    name: str
    url: str | None


class Identity(BaseModel):
    type: str  # "session", "service_key", "user_key"
    provider: str
    provider_user_id: str
    email: str | None
    teams: list[str] | None


class PeopleJobHistory(BaseModel):
    request_id: str
    created_at: float
    updated_at: float
    status: str
    progress: int
    pull_request_url: Optional[str]
