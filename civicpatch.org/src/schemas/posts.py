from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    """A seat a person is asserting exists.

    No `organization_id`: a jurisdiction has one body today, and accepting one would let a
    caller file a post under another jurisdiction's organization. It is resolved server-side
    from the jurisdiction, the same way the derivation does.

    `division_ocdid` is required and creates the division if it is new — a division is minted
    exactly when a post needs one, so folding it in here avoids an endpoint whose only purpose
    is to prepare for this call.
    """

    role_id: str
    division_ocdid: str
    label: str | None = None
    headcount: int = Field(default=1, gt=0)


class UpdatePostRequest(BaseModel):
    """The two fields a person owns.

    Not `role_id` or `division_ocdid`: those are the post's identity, and changing either
    would silently make the next scrape mint a second post rather than match this one.
    """

    label: str | None = None
    headcount: int = Field(default=1, gt=0)
