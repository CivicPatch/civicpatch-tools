import re
from typing import List

from pydantic import BaseModel, field_validator


class RoleInput(BaseModel):
    """A role as the editor submits it. No `id`: an added role's comes from its label, and an
    edit names it in the url. No `priority`: ordering is `PUT /roles/reorder`, admins only."""

    label: str
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


class ReorderRolesRequest(BaseModel):
    role_order: List[str]
    moved_roles: List[str] | None = None
