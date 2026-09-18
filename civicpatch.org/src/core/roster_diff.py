"""What a proposed roster changes against the published one.

Pure. The batch page's per-town counts and the import sheet's `note` column both read this, so
the two cannot disagree. People are matched by id. Memberships are not re-labelled here: their
changes are `ProposedChange`s, which already bound absences to the organizations the changeset read.
"""

from enum import StrEnum

from pydantic import BaseModel

from core.membership_proposal import MembershipDisposition, ProposedChange

# Mirrors the compared entries of `FIELD_SCHEMA` in frontend/components/fields/field-schema.ts,
# in its order. Photo and source urls are `diff: false`; the office is a membership.
_SCALAR_FIELDS = ("name", "start_date", "end_date")
_COMPARED_FIELDS = ("name", "other_names", "start_date", "end_date", "emails", "phones", "urls")


# Mirrors `DiffType` in frontend/utils/diff-utils.js — the two a proposed person can be.
class DiffType(StrEnum):
    ADDED = "added"
    CHANGED = "changed"


class PersonDiff(BaseModel):
    """One person record this roster adds or changes."""

    person_id: str
    name: str
    type: DiffType
    # CHANGED only, in `_COMPARED_FIELDS` order.
    fields: list[str] = []


class ChangeCounts(BaseModel):
    added_people: int = 0
    changed_people: int = 0
    absent_memberships: int = 0


def _scalar(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_set(values: list | None) -> set[str]:
    return {str(value).strip().lower() for value in values or []}


def changed_fields(published: dict, proposed: dict) -> list[str]:
    """Same rule as the card: scalars by trimmed text, lists as case-folded sets."""
    changed = []
    for field in _COMPARED_FIELDS:
        if field in _SCALAR_FIELDS:
            differs = _scalar(published.get(field)) != _scalar(proposed.get(field))
        else:
            differs = _as_set(published.get(field)) != _as_set(proposed.get(field))
        if differs:
            changed.append(field)
    return changed


def person_diffs(published: list[dict], proposed: list[dict]) -> list[PersonDiff]:
    """Every proposed person record that is new or differs. Unchanged people are absent."""
    published_by_id = {person["id"]: person for person in published}
    diffs = []
    for person in proposed:
        before = published_by_id.get(person["id"])
        if before is None:
            diffs.append(
                PersonDiff(person_id=person["id"], name=person.get("name", ""), type=DiffType.ADDED)
            )
            continue
        fields = changed_fields(before, person)
        if fields:
            diffs.append(
                PersonDiff(
                    person_id=person["id"],
                    name=person.get("name", ""),
                    type=DiffType.CHANGED,
                    fields=fields,
                )
            )
    return diffs


UNCHANGED_NOTE = "unchanged"


def _membership_note(proposal: ProposedChange) -> str | None:
    if proposal.disposition is MembershipDisposition.MOVED and proposal.from_post is not None:
        return f"moved from {proposal.from_post.label} to {proposal.post.label}"
    if proposal.disposition is MembershipDisposition.NEW:
        return f"new post: {proposal.post.label}"
    return None


def _person_note(diff: PersonDiff | None, proposals: list[ProposedChange]) -> str:
    parts = []
    if diff is not None and diff.type is DiffType.ADDED:
        parts.append("new person")
    for proposal in proposals:
        note = _membership_note(proposal)
        if note is not None:
            parts.append(note)
    if diff is not None and diff.fields:
        parts.append("changed: " + ", ".join(diff.fields))
    return "; ".join(parts) or UNCHANGED_NOTE


def person_notes(
    person_ids: list[str], diffs: list[PersonDiff], proposals: list[ProposedChange]
) -> dict[str, str]:
    """What this roster changes about each person, most important first: new person, then
    posts, then fields. Absences have no row to note; the batch page counts them."""
    diff_by_id = {diff.person_id: diff for diff in diffs}
    return {
        person_id: _person_note(
            diff_by_id.get(person_id),
            [proposal for proposal in proposals if proposal.person_id == person_id],
        )
        for person_id in person_ids
    }


def count_changes(diffs: list[PersonDiff], proposals: list[ProposedChange]) -> ChangeCounts:
    return ChangeCounts(
        added_people=sum(1 for diff in diffs if diff.type is DiffType.ADDED),
        changed_people=sum(1 for diff in diffs if diff.type is DiffType.CHANGED),
        absent_memberships=sum(
            1 for proposal in proposals if proposal.disposition is MembershipDisposition.ABSENT
        ),
    )
