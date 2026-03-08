from pydantic import BaseModel
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from enum import Enum
import shared.utils.id_utils as id_utils

KNOWN_PLACE_KEYS = ["place", "special_district"]

class RouteCategory(str, Enum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"   # Any valid credential (user API key or session)
    USER = "user"                     # Session only (GUI-specific routes)
    TEAM_MEMBER = "team_member"       # Must belong to "default" team
    SERVICE = "service"               # Service API key only (pipeline/scrape)
    ADMIN = "admin"                   # Admins team only
    MAINTAINER = "maintainer"         # Maintainers team only


@dataclass
class RoutePermission:
    public: bool = False
    allow_service_key: bool = False   # untied to a person, always passes
    allow_user_key: bool = False      # personal API key, teams checked from DB
    allow_session: bool = False       # cookie, teams checked from session
    required_teams: List[str] = field(default_factory=list)  # applied to session + user key

ROUTE_PERMISSIONS = {
    RouteCategory.PUBLIC:        RoutePermission(public=True),
    RouteCategory.USER:          RoutePermission(allow_session=True),
    RouteCategory.AUTHENTICATED: RoutePermission(allow_session=True, allow_user_key=True, allow_service_key=True),
    RouteCategory.TEAM_MEMBER:   RoutePermission(allow_session=True, allow_user_key=True, required_teams=["default"]),
    RouteCategory.ADMIN:         RoutePermission(allow_session=False, allow_user_key=False, allow_service_key=True, required_teams=["admins"]),
    RouteCategory.SERVICE:       RoutePermission(allow_service_key=True),
}

class PullRequest(BaseModel):
    branch_name: str
    jurisdiction_ocdid: str = ""
    url: str

    def model_post_init(self, __context):
        try:
            if not self.jurisdiction_ocdid and self.branch_name:
                self.jurisdiction_ocdid = id_utils.git_branch_to_jurisdiction_ocdid(self.branch_name)
        except Exception as e:
            print(f"git branch does not match jurisdiction id format: {self.branch_name}. Error: {e}")
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