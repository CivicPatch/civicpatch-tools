from pydantic import BaseModel
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from enum import Enum

import shared.utils.id_utils

KNOWN_PLACE_KEYS = ["place", "special_district"]

class RouteCategory(str, Enum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"   # Any valid credential (user API key or session)
    USER = "user"                     # Session only (GUI-specific routes)
    TEAM_MEMBER = "team_member"       # Must belong to "default" team
    SERVICE = "service"               # Service API key only (pipeline/scrape)
    ADMIN = "admin"                   # Admins team only


@dataclass
class RoutePermission:
    public: bool = False
    required_teams: List[str] = field(default_factory=list)
    allow_service_api_key: bool = False
    require_session: bool = False     # GUI-only routes


ROUTE_PERMISSIONS: Dict[RouteCategory, RoutePermission] = {
    RouteCategory.PUBLIC:        RoutePermission(public=True),
    RouteCategory.AUTHENTICATED: RoutePermission(allow_service_api_key=True),
    RouteCategory.USER:          RoutePermission(require_session=True),
    RouteCategory.TEAM_MEMBER:   RoutePermission(required_teams=["default"], require_session=True),
    RouteCategory.SERVICE:       RoutePermission(allow_service_api_key=True),
    RouteCategory.ADMIN:         RoutePermission(required_teams=["admins"], require_session=True),
}

class PullRequest(BaseModel):
    branch_name: str
    jurisdiction_ocdid: str = ""
    url: str

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
    is_service_api_key: bool = False
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