from pydantic import BaseModel, ValidationError
from shared.schemas import Official


class PersonPatch(BaseModel):
    # Every person carries a backend-assigned id: existing people from the data they were
    # loaded with, new people from the Add action. The id is the lookup key — if it matches a
    # base entry we overlay only `fields`; if it doesn't, the person is new and `fields` is
    # the whole entry.
    id: str
    fields: dict


class PeopleValidationError(Exception):
    def __init__(self, failures: list[dict]):  # [{id, name, field, message}]
        super().__init__(f"{len(failures)} person field(s) failed validation")
        self.failures = failures


# Overlay per-person field edits onto the authoritative `base` entries, in `edits` order.
# id in base → overlay only `fields` (everything else untouched); id not in base → new person,
# `fields` inserted whole; base entries absent from `edits` are dropped (deletions). Nothing is
# re-serialized, so untouched fields keep their exact representation.
def apply_people_patch(base: list[dict], edits: list[PersonPatch]) -> list[dict]:
    base_by_id = {entry["id"]: entry for entry in base}
    result = []
    for edit in edits:
        base_entry = base_by_id.get(edit.id)
        if base_entry is None:
            result.append(edit.fields)
        else:
            result.append({**base_entry, **edit.fields})
    return result


# Validate each patched person through `Official` (which also canonicalizes phones and drops
# blank urls), then write the normalized values back — but only for the fields the user
# actually edited (`edit.fields`), so untouched fields keep their exact base representation.
# Raises `PeopleValidationError` (failures keyed by person id) if any person is invalid.
# `patched[i]` corresponds to `edits[i]`.
# The one place that touches pydantic's error encoding. `loc` is the path to the bad value
# — ("phones",), ("phones", 0), ("office", "name") — and its first element is the top-level
# field we surface (loc[-1] would be a list index for list fields).
def _field_errors(exc: ValidationError) -> list[dict]:
    return [
        {"field": str(e["loc"][0]) if e["loc"] else "", "message": e["msg"]}
        for e in exc.errors()
    ]


def validate_and_normalize(patched: list[dict], edits: list[PersonPatch]) -> list[dict]:
    people = []
    failures = []
    for entry, edit in zip(patched, edits):
        try:
            normalized = Official.model_validate(entry).model_dump()
        except ValidationError as exc:
            failures.extend(
                {"id": edit.id, "name": entry.get("name"), **err} for err in _field_errors(exc)
            )
            people.append(entry)
            continue
        edited = {key: normalized[key] for key in edit.fields if key in normalized}
        people.append({**entry, **edited})
    if failures:
        raise PeopleValidationError(failures)
    return people


# Produce the people to write from a base file and a set of edits: overlay, validate,
# normalize. Pure — the caller (router) owns fetching the base and writing the result.
# Raises PeopleValidationError if any edited person is invalid.
def patch_people(base: list[dict], edits: list[PersonPatch]) -> list[dict]:
    return validate_and_normalize(apply_people_patch(base, edits), edits)
