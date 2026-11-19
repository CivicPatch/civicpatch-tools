from pydantic import BaseModel


class CreateOrganizationRequest(BaseModel):
    """A named, non-default body — Council, School Board."""

    name: str
    url: str | None = None


class UpdateOrganizationRequest(BaseModel):
    name: str
    url: str | None
