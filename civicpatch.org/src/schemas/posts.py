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


class MovePostRequest(BaseModel):
    """The body a post belongs to. Must be in the post's own jurisdiction."""

    organization_id: str


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


class AssignMembershipRequest(BaseModel):
    """Assign a person, moving them off any other post in the same body.

    No `organization_id`: it comes from the post, so a request cannot name a mismatched pair.

    No "what happened?" flag either: this is always a transition. Correction (they were never in
    the old post) is its own claim now, `PUT /memberships/{id}/assertion`, which publish applies.
    """

    person_id: str
    post_id: str
    label: str | None = None
    # The caller's own in-progress review, when called from one — otherwise this files under
    # the live roster's changeset instead.
    changeset_id: str | None = None


class AssignmentResult(BaseModel):
    """What an assignment did.

    One `change`, because an assignment does one thing to the seat: `post_id` when they move,
    `label` when they stay and it is renamed. A first assignment is the one whose `post_id`
    change has no `before`, which is what lets a caller say "moved from X" rather than
    "assigned".

    `jurisdiction_ocdid` is carried because mirroring the roster into open-data needs it and
    only `assign` has it — it comes off the post, which its caller never loads.
    """

    membership_id: str
    jurisdiction_ocdid: str
    change: FieldChange
