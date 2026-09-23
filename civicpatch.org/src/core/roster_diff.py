"""What a proposed roster changes against the published one.

Pure. The batch page's per-town counts and the import sheet's `note` column both read this, so
the two cannot disagree. People are matched by id. Memberships are not re-labelled here: their
changes are `ProposedChange`s, which already bound absences to the organizations the changeset read.
"""

from enum import StrEnum

from pydantic import BaseModel

from core.field_diff import changed_fields
from core.membership_proposal import MembershipDisposition, ProposedChange
from shared.utils.name_utils import surname_key


# Mirrors `DiffType` in frontend/utils/diff-utils.js — the two a proposed person can be.
class DiffType(StrEnum):
    ADDED = "added"
    CHANGED = "changed"


class PersonDiff(BaseModel):
    """One person record this roster adds or changes."""

    person_id: str
    name: str
    type: DiffType
    # CHANGED only, in `changed_fields`' order.
    fields: list[str] = []


class ChangeCounts(BaseModel):
    added_people: int = 0
    changed_people: int = 0
    absent_memberships: int = 0


class ProposalCounts(BaseModel):
    """A proposed roster's size and what it changes — one locality's line on the batch page."""

    people: int
    change_counts: ChangeCounts


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


def _person_note(
    diff: PersonDiff | None, proposals: list[ProposedChange], likely_same_as: str | None
) -> str:
    parts = []
    if diff is not None and diff.type is DiffType.ADDED:
        parts.append("new person")
        if likely_same_as:
            parts.append(f"may be {likely_same_as}: add that name to other_names to link them")
    for proposal in proposals:
        note = _membership_note(proposal)
        if note is not None:
            parts.append(note)
    if diff is not None and diff.fields:
        parts.append("changed: " + ", ".join(diff.fields))
    return "; ".join(parts) or UNCHANGED_NOTE


def person_notes(
    person_ids: list[str],
    diffs: list[PersonDiff],
    proposals: list[ProposedChange],
    likely_same: dict[str, str],
) -> dict[str, str]:
    """What this roster changes about each person, most important first: new person, then
    posts, then fields. Absences have no row to note; the batch page counts them."""
    diff_by_id = {diff.person_id: diff for diff in diffs}
    return {
        person_id: _person_note(
            diff_by_id.get(person_id),
            [proposal for proposal in proposals if proposal.person_id == person_id],
            likely_same.get(person_id),
        )
        for person_id in person_ids
    }


def _absent_names(
    published: list[dict], proposed: list[dict], proposals: list[ProposedChange]
) -> dict[str, str]:
    """Published people this roster no longer has at all; someone absent from one post but
    still on the roster has only moved."""
    still_here = {person["id"] for person in proposed}
    absent_ids = {
        proposal.person_id
        for proposal in proposals
        if proposal.disposition is MembershipDisposition.ABSENT
    }
    return {
        person["id"]: person["name"]
        for person in published
        if person["id"] in absent_ids and person["id"] not in still_here
    }


def likely_same_people(
    published: list[dict],
    proposed: list[dict],
    diffs: list[PersonDiff],
    proposals: list[ProposedChange],
) -> dict[str, str]:
    """Each added person the import may have mistaken for an absent one, and the reverse: id to
    the other person's name.

    A pair is the only added and the only absent person sharing a surname. A hint for a human,
    never a match: a relative taking over the post shares one too.
    """
    added = {diff.person_id: diff.name for diff in diffs if diff.type is DiffType.ADDED}
    absent = _absent_names(published, proposed, proposals)
    pairs: dict[str, str] = {}
    for surname in {surname_key(name) for name in added.values()} - {""}:
        added_here = [person_id for person_id, name in added.items() if surname_key(name) == surname]
        absent_here = [person_id for person_id, name in absent.items() if surname_key(name) == surname]
        if len(added_here) != 1 or len(absent_here) != 1:
            continue
        pairs[added_here[0]] = absent[absent_here[0]]
        pairs[absent_here[0]] = added[added_here[0]]
    return pairs


def count_changes(diffs: list[PersonDiff], proposals: list[ProposedChange]) -> ChangeCounts:
    return ChangeCounts(
        added_people=sum(1 for diff in diffs if diff.type is DiffType.ADDED),
        changed_people=sum(1 for diff in diffs if diff.type is DiffType.CHANGED),
        absent_memberships=sum(
            1 for proposal in proposals if proposal.disposition is MembershipDisposition.ABSENT
        ),
    )


def proposal_counts(
    proposed: list[dict], diffs: list[PersonDiff], proposals: list[ProposedChange]
) -> ProposalCounts:
    return ProposalCounts(people=len(proposed), change_counts=count_changes(diffs, proposals))
