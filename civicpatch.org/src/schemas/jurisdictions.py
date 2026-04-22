from typing import List, Literal, Optional

from pydantic import BaseModel


class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]


class RoleEntryWithSource(BaseModel):
    role: str
    is_unique: bool
    aliases: List[str]
    source: Literal["global", "state", "locality"]


class MergedRoleConfigResponse(BaseModel):
    roles: List[RoleEntryWithSource]


class RoleEntryData(BaseModel):
    role: str
    is_unique: bool = False
    aliases: List[str] = []


class SetScopeRolesRequest(BaseModel):
    ocdid: str
    scope: Literal["state", "locality"]
    roles: List[RoleEntryData]
    issue_id: Optional[str] = None
