import re
from typing import List

from pydantic import BaseModel, field_validator

from shared.schemas import RoleStatus


class RoleInput(BaseModel):
    """A role as submitted. No `id` — it is derived from the label on insert.

    No `priority` either: ordering is owned by `PUT /roles/reorder`, which is
    ADMINS-only, and accepting it here would both let a MAINTAINER set ordering
    through the upsert path and make an omitted field read as "clear it".
    Reads use `shared.schemas.Role`, which carries both.
    """

    label: str
    status: RoleStatus = RoleStatus.ACTIVE
    is_unique: bool = False
    aliases: List[str] = []

    @field_validator("label")
    @classmethod
    def label_must_yield_a_slug(cls, value: str) -> str:
        # `roles.id` is slugify_label(label), which keeps only alphanumerics. A
        # label made purely of punctuation slugs to "", and an empty primary key
        # is published identity that means nothing.
        if not re.search(r"[a-zA-Z0-9]", value):
            raise ValueError("Label must contain at least one letter or digit.")
        return value


class SetRolesRequest(BaseModel):
    roles: List[RoleInput]
    # Set when the write resolves a pipeline issue (an unrecognized role the
    # maintainer is accepting into the taxonomy).
    issue_id: str | None = None


class ReorderRolesRequest(BaseModel):
    role_order: List[str]
    moved_roles: List[str] | None = None
