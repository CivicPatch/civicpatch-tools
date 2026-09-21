"""The id a claim about a membership names.

A membership is a `(person, post)` pair with no row of its own, so its id is a pure function
of the two identities. Any writer can mint it without a lookup, and it survives every rebuild
of the projection.

Shared because both sides must agree exactly: the route that files the claim and the fold that
resolves it. A mismatch is a claim that resolves against nothing and fails silently.
"""

import uuid

MEMBERSHIP_NAMESPACE = uuid.UUID("5364ee76-7dec-41fd-a3b0-7218a73ea92f")

# A person id is a uuid, so it cannot contain the separator and the encoding is unambiguous.
_SEPARATOR = "|"


def membership_id(person_id: str, post_id: str) -> str:
    return str(uuid.uuid5(MEMBERSHIP_NAMESPACE, f"{person_id}{_SEPARATOR}{post_id}"))
