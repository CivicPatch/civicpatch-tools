from pydantic import BaseModel, ValidationError
from schemas.assertions import AssertionKind
from shared.schemas import Official
from shared.utils.official_fields import order_official_fields


# Every field a reviewer can edit on a person, which is exactly what the change log diffs: a
# field missing here is a field whose edit goes unrecorded.
#
# Not `post_id`: where somebody serves is a membership, and its id is a uuid the activity feed
# would print raw. Not `cdn_image`: publish writes it from `image`.
EDITABLE_FIELDS = (
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "image",
    "start_date",
    "end_date",
)

# Of those, the ones holding several values: a list field is a set, so `phones` carries many
# accepts where `name` carries one. Mirrors the two partial unique indexes in 137.
LIST_FIELDS = frozenset({"other_names", "phones", "emails", "urls", "source_urls"})


def with_stated_values(person: dict, stated: dict) -> dict:
    """`published = (scraped ∪ accepted) − rejected`, per field.

    A reject suppresses one *value*, never the field, so the scraper keeps looking and something
    it has never found still reaches a reviewer. Scraped order first, then accepted.

    A scalar cannot union, so an accept replaces it and a reject empties it.
    """
    published = dict(person)
    for field, by_kind in stated.items():
        if field not in EDITABLE_FIELDS:
            continue
        accepted = by_kind.get(AssertionKind.ACCEPT) or []
        rejected = by_kind.get(AssertionKind.REJECT) or []

        if field in LIST_FIELDS:
            kept = [value for value in (person.get(field) or []) if value not in rejected]
            published[field] = kept + [
                value for value in accepted if value not in kept and value not in rejected
            ]
        elif accepted:
            published[field] = accepted[0]
        elif person.get(field) in rejected:
            published[field] = None
    return published


def values_to_accept(person: dict) -> list[tuple[str, object]]:
    """Every value on a published person a human could have looked at, one entry per value so a
    list field yields one per element.

    A field they saw blank stays the scraper's — and `value` is NOT NULL.
    """
    accepted: list[tuple[str, object]] = []
    for field in EDITABLE_FIELDS:
        value = person.get(field)
        if field in LIST_FIELDS:
            accepted.extend((field, item) for item in (value or []) if item)
        elif value is not None and value != "":
            accepted.append((field, value))
    return accepted


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


def _person_errors(edit: PersonPatch, entry: dict, errors: list[dict]) -> list[dict]:
    return [{"id": edit.id, "name": entry.get("name"), **err} for err in errors]


# A submission rule, not a data-model one: `Official` is also built by the pipelines
# (person_to_official), where a scrape that saw the same email twice has no user to alert
# and must not fail. Blank keys are falsy, so two empty rows are not a duplicate.
def _duplicate_errors(entry: dict) -> list[dict]:
    errors = []
    for field, values in entry.items():
        if not isinstance(values, list):
            continue
        seen = set()
        for value in values:
            key = str(value).strip().lower()
            if key and key in seen:
                errors.append({"field": field, "message": f"'{value}' is listed twice"})
            seen.add(key)
    return errors


# Also a submission rule rather than a data-model one, and for the same reason: a scrape
# that found no source must still produce a record, but a person published through the
# editor is unverifiable without one. FIELD_SCHEMA marks it required on the client.
def _missing_source_errors(entry: dict) -> list[dict]:
    if any(str(url).strip() for url in entry.get("source_urls") or []):
        return []
    return [{"field": "source_urls", "message": "At least one source url is required"}]


def validate_and_normalize(patched: list[dict], edits: list[PersonPatch]) -> list[dict]:
    people = []
    failures = []
    for entry, edit in zip(patched, edits):
        try:
            normalized = Official.model_validate(entry).model_dump()
        except ValidationError as exc:
            failures.extend(_person_errors(edit, entry, _field_errors(exc)))
            people.append(entry)
            continue
        # Against the normalized entry, so two spellings of one phone number are caught
        # after canonicalization rather than read as two numbers.
        errors = _duplicate_errors(normalized) + _missing_source_errors(normalized)
        if errors:
            failures.extend(_person_errors(edit, entry, errors))
            people.append(entry)
            continue
        edited = {key: normalized[key] for key in edit.fields if key in normalized}
        people.append({**entry, **edited})
    if failures:
        raise PeopleValidationError(failures)
    return people


# Produce the people to write from a base file and a set of edits: overlay, validate,
# normalize, order. Pure — the caller (router) owns fetching the base and writing the result.
# Raises PeopleValidationError if any edited person is invalid.
def patch_people(base: list[dict], edits: list[PersonPatch]) -> list[dict]:
    patched = validate_and_normalize(apply_people_patch(base, edits), edits)
    return [order_official_fields(person) for person in patched]
