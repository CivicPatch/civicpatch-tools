from pydantic import BaseModel


class CreateOrganizationRequest(BaseModel):
    """A named, non-default body — Council, School Board."""

    name: str
    url: str | None = None


class UpdateOrganizationRequest(BaseModel):
    name: str
    url: str | None
    # Role id -> what this organization calls the role; left out, the labels stay as they are.
    extras_role_labels: dict[str, str] | None = None
