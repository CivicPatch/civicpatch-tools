from typing import List, Literal, Optional

from pydantic import BaseModel, Field
from shared.schemas import Role

Scope = Literal["global", "state", "locality"]
WritableScope = Literal["state", "locality"]  # global has its own endpoints


class ScopedRole(Role):
    scope: Scope


class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]


class MergedRoleConfigResponse(BaseModel):
    roles: List[ScopedRole]


class SetScopeRolesRequest(BaseModel):
    ocdid: str
    scope: WritableScope
    roles: List[Role]
    issue_id: Optional[str] = None


class SetGlobalRolesRequest(BaseModel):
    roles: List[Role]


class ReorderGlobalRolesRequest(BaseModel):
    role_order: List[str]  # canonical role values, desired order (priority 0..N)
    moved_roles: List[
        str
    ] = []  # values the user actively moved (for the audit summary)


class ReorderScopeRolesRequest(BaseModel):
    ocdid: str
    scope: Literal["state", "locality"]
    role_order: List[str]  # canonical role values, desired order (priority 0..N)
    moved_roles: List[
        str
    ] = []  # values the user actively moved (for the audit summary)


class RoleScopeRequest(BaseModel):
    """Base for operations targeting a single role at a given scope."""

    role: str
    scope: Literal["global", "state", "locality"]
    ocdid: str = ""  # ignored for global scope


class DeleteRoleRequest(RoleScopeRequest):
    pass


class JurisdictionSearchResult(BaseModel):
    jurisdiction_ocdid: str
    level: str
    # Display names of the row's parent_ocdids, most specific first — e.g.
    # ["King County", "Washington"]. The ocdid carries only slugs, and a slug's display
    # name lives on the parent's own row, so this cannot be derived client-side.
    # Empty where open-data records no parents (all of NC and TN, some of MI/NJ).
    parent_names: list[str] = []
    # Official name, Census type suffix intact ("Albion township"). The suffix
    # disambiguates — MI has an Albion city and an Albion township.
    name: str
    # Friendly form ("Albion"). Absent until open-data emits it; callers fall back.
    display_name: str | None = None
    population: int | None = None


class PaginationLinks(BaseModel):
    # "self" is unusable as an attribute name, so serialize under the alias. FastAPI
    # dumps response models by alias, matching the envelope /{state}/search returns.
    prev: str = ""
    next: str = ""
    self_link: str = Field("", alias="self")


class JurisdictionSearchResponse(BaseModel):
    total_items: int
    page: int
    total_pages: int
    limit: int
    data: list[JurisdictionSearchResult]
    links: PaginationLinks
