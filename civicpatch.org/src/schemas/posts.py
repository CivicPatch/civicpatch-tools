from pydantic import BaseModel, Field


class CreatePostRequest(BaseModel):
    """A post a person is asserting exists.

    No `organization_id`: a jurisdiction has one body today, and accepting one would let a
    caller file a post under another jurisdiction's organization. It is resolved server-side
    from the jurisdiction, the same way the derivation does.

    `division_ocdid` is required and creates the division if it is new — a division is minted
    exactly when a post needs one, so folding it in here avoids an endpoint whose only purpose
    is to prepare for this call.
    """

    role_id: str
    division_ocdid: str
    # Aliased like the update route's, so the field has one name on the wire whichever way it
    # is crossed. Defaulted, unlike there: a new post is one seat unless someone says otherwise.
    headcount: int = Field(default=1, alias="_headcount", gt=0)


class UpdatePostRequest(BaseModel):
    """The fields a person owns.

    Not `role_id` or `division_ocdid`: those are the post's identity, and changing either
    would silently make the next scrape mint a second post rather than match this one.

    Not `label` either, since 148: it is composed from the role and the division on read, so
    there is nothing here to set.
    """

    # Underscored on the wire: no civic standard defines either of these, so a consumer
    # dropping every `_*` key is left with a conforming record. The columns are plain — the
    # distinction is about what we emit — so the alias is where it gets applied.
    #
    # Required, like the identity fields on create: this route replaces what it is given, and
    # a default would let an omission silently re-track a post somebody turned off.
    headcount: int = Field(alias="_headcount", gt=0)
    is_tracked: bool = Field(alias="_is_tracked")


class AssignMembershipRequest(BaseModel):
    """Assign a person, moving them off any other post in the same body.

    No `organization_id`: it comes from the post, so a request cannot name a mismatched pair.

    No "what happened?" flag either — this is always a transition. Correction (they were never
    in the old post) needs the publish merge to apply `assertions`, which is not built yet:
    until it does, the next scrape re-derives the old membership, and offering the option would
    let a curator believe they fixed history when it will be undone within the week.
    """

    person_id: str
    post_id: str
    label: str | None = None
