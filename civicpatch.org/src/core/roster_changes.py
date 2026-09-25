"""What one roster changes against another, person by person.

Pure, and over the two sides a review card already presents (`core.display_rows`): the sheet's
`note` column, the report tab and the batch page's counts all read one answer, so the three
cannot disagree about what an import did.

Not `core.projection.diff`, which answers whether two rosters differ at all (R6, the dry run,
the history loop). This answers what a person would be *told* changed, which is a narrower
field set and a coarser membership comparison.

Offices compare per organization, which is where the model puts them: somebody holds one office
per organization, so the same organization with a different post is a move rather than a drop
and an add.
"""

from enum import StrEnum

from pydantic import BaseModel

from core.field_diff import changed_fields
from shared.utils.name_utils import surname_key

UNCHANGED_NOTE = "unchanged"


class OfficeChangeKind(StrEnum):
    NEW = "new"
    MOVED = "moved"
    ABSENT = "absent"


class OfficeChange(BaseModel):
    kind: OfficeChangeKind
    organization_id: str
    post_label: str
    # MOVED only: the post they held in this organization before.
    from_post_label: str | None = None


class ChangeKind(StrEnum):
    """One person's headline, most severe first. The values are the report tab's own text."""

    ADDED = "added"
    ABSENT = "absent"
    MOVED = "moved"
    NEW_POST = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class PersonDiff(BaseModel):
    """What this roster changes about one person: what happened to them, and to their offices.

    Not `schemas.activity.PersonChange`, which is one activity-log event. This is a comparison,
    and it has an entry for everyone either roster lists, `UNCHANGED` included — the sheet's
    note column needs a line per row, not only per change.
    """

    person_id: str
    name: str
    added: bool = False
    # On the proposed roster at all. False is somebody it drops entirely.
    listed: bool = True
    # In `changed_fields`' order.
    fields: list[str] = []
    offices: list[OfficeChange] = []

    @property
    def kind(self) -> ChangeKind:
        if self.added:
            return ChangeKind.ADDED
        kinds = {office.kind for office in self.offices}
        if OfficeChangeKind.ABSENT in kinds:
            return ChangeKind.ABSENT
        if OfficeChangeKind.MOVED in kinds:
            return ChangeKind.MOVED
        if OfficeChangeKind.NEW in kinds:
            return ChangeKind.NEW_POST
        return ChangeKind.CHANGED if self.fields else ChangeKind.UNCHANGED


def _offices(row: dict) -> dict[str, dict]:
    return {
        membership["organization_id"]: membership
        for membership in row.get("memberships") or []
    }


def _office_changes(before: dict, after: dict) -> list[OfficeChange]:
    held = _offices(before)
    proposed = _offices(after)
    changes = []
    for organization_id, membership in proposed.items():
        was = held.get(organization_id)
        if was is None:
            changes.append(
                OfficeChange(
                    kind=OfficeChangeKind.NEW,
                    organization_id=organization_id,
                    post_label=membership["post_label"],
                )
            )
        elif was["post_id"] != membership["post_id"]:
            changes.append(
                OfficeChange(
                    kind=OfficeChangeKind.MOVED,
                    organization_id=organization_id,
                    post_label=membership["post_label"],
                    from_post_label=was["post_label"],
                )
            )
    for organization_id, was in held.items():
        if organization_id not in proposed:
            changes.append(
                OfficeChange(
                    kind=OfficeChangeKind.ABSENT,
                    organization_id=organization_id,
                    post_label=was["post_label"],
                )
            )
    return changes


def _change_of(before: dict | None, after: dict | None) -> PersonDiff:
    record = after or before or {}
    return PersonDiff(
        person_id=record["id"],
        name=record.get("name") or "",
        added=before is None,
        listed=after is not None,
        fields=changed_fields(before, after) if before and after else [],
        offices=_office_changes(before or {}, after or {}),
    )


def changes_of(published: list[dict], proposed: list[dict]) -> list[PersonDiff]:
    """One entry per person either side lists: the proposed roster in its own order, then
    whoever it drops."""
    published_by_id = {person["id"]: person for person in published}
    proposed_ids = {person["id"] for person in proposed}
    changes = [
        _change_of(published_by_id.get(person["id"]), person) for person in proposed
    ]
    for person in published:
        if person["id"] not in proposed_ids:
            changes.append(_change_of(person, None))
    return changes


def _office_note(office: OfficeChange) -> str | None:
    if office.kind is OfficeChangeKind.MOVED:
        return f"moved from {office.from_post_label} to {office.post_label}"
    if office.kind is OfficeChangeKind.NEW:
        return f"new post: {office.post_label}"
    return None


def note_of(change: PersonDiff, likely_same_as: str | None) -> str:
    parts = []
    if change.added:
        parts.append("new person")
        if likely_same_as:
            parts.append(f"may be {likely_same_as}: add that name to other_names to link them")
    for office in change.offices:
        note = _office_note(office)
        if note is not None:
            parts.append(note)
    if change.fields:
        parts.append("changed: " + ", ".join(change.fields))
    return "; ".join(parts) or UNCHANGED_NOTE


def person_notes(
    changes: list[PersonDiff], likely_same: dict[str, str]
) -> dict[str, str]:
    """What this roster changes about each person still listed, most important first: new
    person, then offices, then fields. A dropped person has no row to note."""
    return {
        change.person_id: note_of(change, likely_same.get(change.person_id))
        for change in changes
        if change.listed
    }


def likely_same_people(changes: list[PersonDiff]) -> dict[str, str]:
    """Each added person this roster may have mistaken for a dropped one, and the reverse: id to
    the other person's name.

    A pair is the only added and the only dropped person sharing a surname. A hint for a human,
    never a match: a relative taking over the post shares one too.
    """
    added = {change.person_id: change.name for change in changes if change.added}
    dropped = {change.person_id: change.name for change in changes if not change.listed}
    pairs: dict[str, str] = {}
    for surname in {surname_key(name) for name in added.values()} - {""}:
        added_here = [
            person_id for person_id, name in added.items() if surname_key(name) == surname
        ]
        dropped_here = [
            person_id for person_id, name in dropped.items() if surname_key(name) == surname
        ]
        if len(added_here) != 1 or len(dropped_here) != 1:
            continue
        pairs[added_here[0]] = dropped[dropped_here[0]]
        pairs[dropped_here[0]] = added[added_here[0]]
    return pairs


class ChangeCounts(BaseModel):
    added_people: int = 0
    changed_people: int = 0
    absent_memberships: int = 0


class ProposalCounts(BaseModel):
    """A proposed roster's size and what it changes — one locality's line on the batch page.

    Stored as `changesets.proposal_counts`, so this shape is a persisted one.
    """

    people: int
    change_counts: ChangeCounts


def count_changes(changes: list[PersonDiff]) -> ChangeCounts:
    return ChangeCounts(
        added_people=sum(1 for change in changes if change.added),
        changed_people=sum(
            1 for change in changes if not change.added and change.fields
        ),
        absent_memberships=sum(
            1
            for change in changes
            for office in change.offices
            if office.kind is OfficeChangeKind.ABSENT
        ),
    )


def proposal_counts(changes: list[PersonDiff]) -> ProposalCounts:
    return ProposalCounts(
        people=sum(1 for change in changes if change.listed),
        change_counts=count_changes(changes),
    )
