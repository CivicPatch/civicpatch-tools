from pydantic import BaseModel
from typing import Optional
from enum import Enum

import shared.utils.id_utils

KNOWN_PLACE_KEYS = ["place", "special_district"]


class ApiKeyType(str, Enum):
    WIDGET_KEY = "widget_key"      # TODO: Implement
    SERVER_KEY = "server_key"      # For internal server operations
    INTERNAL_SERVER_KEY = "internal_key"


class UserRole(str, Enum):
    ADMIN = "admin"
    JOBS = "jobs"
    MEMBER = "member"
    UNVERIFIED = "unverified"


class RouteCategory(str, Enum):
    COMPONENT_API = "component_api"    # Widget/component routes (was public_widget)
    INTERNAL_API = "internal_api"      # Internal server operations  
    ADMIN_ONLY = "admin_only"         # Admin-only routes
    JOBS_API = "jobs_api"        # Routes for /api/v1/jobs/people


class Person(BaseModel):
    name: str
    jurisdiction_ocdid: str

    class Config:
        extra = "allow"

class PullRequest(BaseModel):
    branch_name: str
    jurisdiction_ocdid: str = ""

    def model_post_init(self, __context):
        try:
            if not self.jurisdiction_ocdid and self.branch_name:
                self.jurisdiction_ocdid = shared.utils.id_utils.git_branch_to_jurisdiction_ocdid(self.branch_name)
        except Exception:
            print(f"git branch does not match jurisdiciton id format: {self.branch_name}")
            self.jurisdiction_ocdid = ""

class Jurisdiction(BaseModel):
    id: str
    name: str
    url: str | None

class Identity(BaseModel):
    provider: str
    provider_user_id: str
    email: str | None
    roles: list[str] | None

class PeopleJobHistory(BaseModel):
    request_id: str
    created_at: float
    updated_at: float
    status: str
    progress: int
    pull_request_url: Optional[str]