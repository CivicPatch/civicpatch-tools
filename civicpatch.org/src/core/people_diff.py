from collections.abc import Mapping
from typing import Any

from core.change_logs import field_changes
from core.people_edits import EDITABLE_FIELDS
from shared.schemas import POST_FIELD
from schemas.assertions import EntityType
from schemas.change_logs import Change, FieldChange, PersonChange
from shared.utils.statuses import ChangeLogType


# `id` is the match key, not a field. Everything else a reviewer can touch is here, because a
# field left out is an edit the feed silently never mentions — which is what `office.name` and
# `office.division_ocdid` became when the editor started writing `post_id` instead, and what
# `image`, `source_urls` and `other_names` were all along, excluded as noise back when the
# reviewer could not edit them.
def _comparable(person: dict, post_labels: Mapping[str, str] = {}) -> dict[str, Any]:
    """The person as the feed compares them — with the picked post named, not identified.

    A `post_id` is a uuid, and the feed prints what it is given: "post_id: ∅ → 3b0c2e2d-…" says
    nothing a reader can act on. Labels are resolved by the caller and substituted here, so the
    log records what the change *meant* at the time, which is what an append-only history is
    for.
    """
    comparable = {field: person.get(field) for field in EDITABLE_FIELDS}
    post_id = comparable.get(POST_FIELD)
    if post_id:
        comparable[POST_FIELD] = post_labels.get(post_id, post_id)
    return comparable


def diff_people(
    before: list[dict],
    after: list[dict],
    post_labels: Mapping[str, str] | None = None,
) -> list[PersonChange]:
    labels = post_labels or {}
    before_by_id = {person["id"]: person for person in before}
    after_by_id = {person["id"]: person for person in after}

    changes: list[PersonChange] = []
    added: list[dict] = []
    for person_id, after_person in after_by_id.items():
        before_person = before_by_id.get(person_id)
        if before_person is None:
            added.append(after_person)
            continue
        changed_fields = field_changes(
            _comparable(before_person, labels), _comparable(after_person, labels)
        )
        if changed_fields:
            changes.append(_edited(after_person, changed_fields))

    removed = [p for pid, p in before_by_id.items() if pid not in after_by_id]

    # Re-link reconciliation: matching a person to an existing record changes their
    # id, which looks like an add + a delete. When the content is identical, it's the
    # same person re-linked, not a real change — cancel those pairs out.
    added, removed = _cancel_relinks(added, removed)

    changes.extend(_added(person, labels) for person in added)
    changes.extend(_removed(person, labels) for person in removed)
    return changes


def _cancel_relinks(added: list[dict], removed: list[dict]) -> tuple[list[dict], list[dict]]:
    remaining_removed = list(removed)
    real_added: list[dict] = []
    for after_person in added:
        match = next(
            # Unlabelled on both sides: this only asks whether two records are the same person.
            (p for p in remaining_removed if _comparable(p) == _comparable(after_person)),
            None,
        )
        if match is None:
            real_added.append(after_person)
        else:
            remaining_removed.remove(match)
    return real_added, remaining_removed


def _added(person: dict, post_labels: Mapping[str, str]) -> PersonChange:
    fields = [
        FieldChange(field=field, after=value)
        for field, value in _comparable(person, post_labels).items()
        if value
    ]
    return PersonChange(type=ChangeLogType.ADD_PERSON, payload=_payload(person, fields))


def _removed(person: dict, post_labels: Mapping[str, str]) -> PersonChange:
    fields = [
        FieldChange(field=field, before=value)
        for field, value in _comparable(person, post_labels).items()
        if value
    ]
    return PersonChange(type=ChangeLogType.DELETE_PERSON, payload=_payload(person, fields))


def _edited(person: dict, fields: list[FieldChange]) -> PersonChange:
    return PersonChange(type=ChangeLogType.EDIT_PERSON, payload=_payload(person, fields))


def _payload(person: dict, fields: list[FieldChange]) -> Change:
    return Change(
        entity_type=EntityType.PERSON,
        entity_id=person["id"],
        subject=person.get("name") or "",
        fields=fields,
    )
