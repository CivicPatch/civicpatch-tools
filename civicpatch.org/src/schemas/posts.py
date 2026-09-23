from enum import StrEnum

from pydantic import BaseModel, Field
from schemas.activity import FieldChange


class CreatePostRequest(BaseModel):
    """A post a person is asserting exists, under the organization named by the route.

    `division_ocdid` is required and creates the division if it is new — a division is minted
    exactly when a post needs one, so folding it in here avoids an endpoint whose only purpose
    is to prepare for this call.
    """

    role_id: str
    division_ocdid: str
    # Defaulted, unlike the update route's: a new post is one seat unless someone says otherwise.
    meta_headcount: int = Field(default=1, gt=0)
    # Overrides the derived guess ("Position 8" instead of the bare role) — asserted, like
    # `meta_headcount`, not stored as its own column (148 dropped `posts.label`).
    label: str | None = None


class UpdatePostRequest(BaseModel):
    """The fields a person owns.

    Not `role_id` or `division_ocdid`: those are the post's identity, and changing either
    would silently make the next scrape mint a second post rather than match this one.

    Not `label` either, since 148: it is composed from the role and the division on read, so
    there is nothing here to set.
    """

    # Required, like the identity fields on create: this route replaces what it is given, and
    # a default would let an omission silently re-track a post somebody turned off.
    meta_headcount: int = Field(gt=0)
    meta_is_tracked: bool


class MembershipRemovalAssertion(StrEnum):
    """Which assertion takes a membership off the roster. Narrower than "an assertion about a
    membership", which also covers its label and whatever else a person can claim about one.

    One of three, because the two removals contradict each other: a membership that never held did
    not also close, and either withdraws the other."""

    NONE = "none"
    CLOSED = "closed"
    NEVER_HELD = "never_held"


class MembershipRemovalRequest(BaseModel):
    """What a person says about a membership, or about someone being a member here at all.

    `reason` rides as the assertion's `sources` note, the "phoned the clerk" case. `changeset_id`
    files it under a review in progress, so dismissing that review takes it with it.
    """

    assertion: MembershipRemovalAssertion = MembershipRemovalAssertion.NONE
    reason: str | None = None
    changeset_id: str | None = None



