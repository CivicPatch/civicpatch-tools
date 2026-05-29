from typing import List, Literal, Optional

from pydantic import BaseModel


class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]


RoleKind = Literal["canonical", "exclusion"]


class RoleEntryWithSource(BaseModel):
    role: str
    is_unique: bool
    aliases: List[str]
    kind: RoleKind = "canonical"
    source: Literal["global", "state", "locality"]


class MergedRoleConfigResponse(BaseModel):
    roles: List[RoleEntryWithSource]


class RoleEntryData(BaseModel):
    role: str
    is_unique: bool = False
    aliases: List[str] = []
    kind: RoleKind = "canonical"


class SetScopeRolesRequest(BaseModel):
    ocdid: str
    scope: Literal["state", "locality"]
    roles: List[RoleEntryData]
    issue_id: Optional[str] = None


class SetGlobalRolesRequest(BaseModel):
    roles: List[RoleEntryData]


class RoleScopeRequest(BaseModel):
    """Base for operations targeting a single role at a given scope."""
    role: str
    scope: Literal["global", "state", "locality"]
    ocdid: str = ""  # ignored for global scope


class ExcludeRoleRequest(RoleScopeRequest):
    pass


class DeleteRoleRequest(RoleScopeRequest):
    pass


class IncludeExclusionRequest(BaseModel):
    """Move an exclusion pattern back to roles."""
    value: str
    scope: Literal["global", "state", "locality"]
    ocdid: str = ""  # ignored for global scope
    is_unique: bool = False
