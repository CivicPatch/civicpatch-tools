from typing import Any

from schemas.change_logs import FieldChange, PersonChange, PersonChangePayload
from shared.utils.statuses import ChangeLogType


# The human-meaningful leaf fields we diff, flattened. `id` is the match key; office is
# split into its components; source_urls/image are excluded as noise.
def _comparable(person: dict) -> dict[str, Any]:
    office = person.get("office") or {}
    return {
        "name": person.get("name"),
        "office.name": office.get("name"),
        "office.division_ocdid": office.get("division_ocdid"),
        "emails": person.get("emails"),
        "phones": person.get("phones"),
        "urls": person.get("urls"),
        "start_date": person.get("start_date"),
        "end_date": person.get("end_date"),
    }


def diff_people(existing: list[dict], published: list[dict]) -> list[PersonChange]:
    existing_by_id = {person["id"]: person for person in existing}
    published_by_id = {person["id"]: person for person in published}

    changes: list[PersonChange] = []
    for person_id, after in published_by_id.items():
        before = existing_by_id.get(person_id)
        if before is None:
            changes.append(_added(after))
            continue
        field_changes = _field_changes(_comparable(before), _comparable(after))
        if field_changes:
            changes.append(_edited(after, field_changes))

    for person_id, before in existing_by_id.items():
        if person_id not in published_by_id:
            changes.append(_removed(before))

    return changes


def _field_changes(before: dict[str, Any], after: dict[str, Any]) -> list[FieldChange]:
    return [
        FieldChange(field=field, from_=before[field], to=after[field])
        for field in before
        if before[field] != after[field]
    ]


def _added(person: dict) -> PersonChange:
    fields = [FieldChange(field=field, to=value) for field, value in _comparable(person).items() if value]
    return PersonChange(type=ChangeLogType.ADD_PERSON, payload=_payload(person, fields))


def _removed(person: dict) -> PersonChange:
    fields = [FieldChange(field=field, from_=value) for field, value in _comparable(person).items() if value]
    return PersonChange(type=ChangeLogType.DELETE_PERSON, payload=_payload(person, fields))


def _edited(person: dict, fields: list[FieldChange]) -> PersonChange:
    return PersonChange(type=ChangeLogType.EDIT_PERSON, payload=_payload(person, fields))


def _payload(person: dict, fields: list[FieldChange]) -> PersonChangePayload:
    return PersonChangePayload(person_id=person["id"], person_name=person.get("name") or "", fields=fields)
