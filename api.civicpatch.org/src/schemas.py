from pydantic import BaseModel, model_validator

from civicpatch.id_utils import git_branch_to_jurisdiction_id

KNOWN_PLACE_KEYS = ["place", "special_district"]


class Person(BaseModel):
    name: str
    jurisdiction_id: str

    class Config:
        extra = "allow"


class PullRequest(BaseModel):
    branch_name: str
    jurisdiction_id: str = ""

    @model_validator(mode="after")
    def set_jurisdiction_id(self):
        try:
            if not self.jurisdiction_id and self.branch_name:
                self.jurisdiction_id = git_branch_to_jurisdiction_id(self.branch_name)
        except Exception:
            print(f"git branch does not match jurisdiciton id format: {self.branch_name}")
            self.jurisdiction_id = ""
        return self


class Jurisdiction(BaseModel):
    id: str
    name: str
    url: str | None

class Identity(BaseModel):
    provider: str
    provider_user_id: str
    email: str | None
    role: str | None