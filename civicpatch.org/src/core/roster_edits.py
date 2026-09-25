"""What a roster edit means, as claims. Pure: the derived roster and the client's edit in.

The shell that loads the roster, mints the changeset and writes is `services/roster_edits.py`.
"""

from core.people_edits import (
    PersonPatch,
    claims_from_edit,
    claims_from_posts,
    patch_people,
)
from core.projection.memberships import (
    MEMBERSHIP_END_DATE_FIELD,
    MEMBERSHIP_LABEL_FIELD,
    MEMBERSHIP_START_DATE_FIELD,
)
from schemas.claims import Claim
from schemas.jurisdictions import PersonEdit
from shared.utils.membership_ids import membership_id


def new_merges(derived: dict[str, dict], people: list[PersonEdit]) -> dict[str, str]:
    """Absorbed id to survivor id, for merges not yet filed: once merged, an id derives no row."""
    return {
        person.id: person.same_as
        for person in people
        if person.same_as is not None and person.id in derived
    }


def claims_for_edit(
    derived: dict[str, dict], people: list[PersonEdit], changeset_id: str
) -> list[Claim]:
    """Pure: the derived roster keyed by person id, and what the client says, in; claims out.

    A person the roster does not derive is an addition, so they have nothing to diff against.
    """
    # Validated and canonicalized before the diff, the way the review save has always done it:
    # a reviewer reformatting a phone the scrape already found must file nothing, and an
    # invalid field must be refused rather than claimed.
    patches = [
        PersonPatch(id=person.id, fields=person.fields)
        for person in people
        if person.fields
    ]
    desired = {
        entry["id"]: entry
        for entry in (patch_people(list(derived.values()), patches) if patches else [])
    }

    claims: list[Claim] = []
    for person in people:
        if person.same_as is not None:
            continue
        published = derived.get(person.id, {"id": person.id})
        if person.id in desired:
            claims.extend(
                claims_from_edit(
                    person.id, published, desired[person.id], changeset_id
                )
            )
        if person.offices is not None:
            claims.extend(
                claims_from_posts(
                    person.id,
                    [post["post_id"] for post in published.get("memberships") or []],
                    [office.id for office in person.offices],
                    changeset_id,
                )
            )
    return claims


# Each office field, and the membership claim it is filed under.
_CLAIMED_OFFICE_FIELDS = {
    "membership_label": MEMBERSHIP_LABEL_FIELD,
    "start_date": MEMBERSHIP_START_DATE_FIELD,
    "end_date": MEMBERSHIP_END_DATE_FIELD,
}


def membership_claim_edits(
    derived: dict[str, dict], people: list[PersonEdit]
) -> list[tuple[str, str, str | None]]:
    """`(membership_id, field, value)` for each label or term date this edit changes.

    Not claims, because clearing one is a withdrawal, and a withdrawal names a row rather than a
    value. `memberships.set_membership_field` files both halves, so the shell calls it.
    """
    changes = []
    for person in people:
        held = {
            post["post_id"]: post
            for post in (derived.get(person.id) or {}).get("memberships") or []
        }
        for office in person.offices or []:
            was = held.get(office.id) or {}
            # Only what the client sent: an office sent to keep a person's other body names no dates.
            for key, now in office.model_dump(exclude_unset=True, exclude={"id"}).items():
                field = _CLAIMED_OFFICE_FIELDS[key]
                if now != was.get(field):
                    changes.append((membership_id(person.id, office.id), field, now))
    return changes
