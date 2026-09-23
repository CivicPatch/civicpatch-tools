from collections.abc import Iterable

from pydantic import BaseModel, ValidationError
from schemas.assertions import (
    DefaultNote,
    Assertion,
    AssertionKind,
    EntityType,
    Source,
)
from shared.schemas import SubmittedPersonRecord
from shared.utils.person_fields import order_person_fields

from core.post_derivation import LABELS_FIELD, SIGHTINGS_FIELD

# Keys a client patch may not set: they come from source records, and a client-sent value would
# decide which organization a person is published into.
SERVER_OWNED_FIELDS = (SIGHTINGS_FIELD, LABELS_FIELD)

# Fields a reviewer can edit — a missing one goes unrecorded in the change log. Not
# cdn_image; publish derives it from image. Which posts somebody holds is `POSTS_FIELD`, its
# own multi-valued claim, not a field here.
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

# Fields whose change during a scrape raises a review issue — not what the diff shows,
# which is anything that differs.
SURFACED_FIELDS = ("name",)

# Multi-valued fields. Mirrors the two partial unique indexes in migration 137.
LIST_FIELDS = frozenset({"other_names", "phones", "emails", "urls", "source_urls"})

# Which posts somebody holds: one claim per post, the post's id as the value, accept or
# reject. Multi-valued for the same reason a phone is — somebody can hold two. Not editable: a
# patch cannot set it, because a scrape stays free to move or end a membership.
POSTS_FIELD = "posts"
# Derived from the sightings now, so editing it states nothing about the world.
NOT_ASSERTABLE = frozenset({"source_urls"})

# A blank date means unknown/still-serving, not wrong — suppress the reject only.
NOT_REJECTABLE = frozenset({"start_date", "end_date"})


def _values_of(value: object) -> list:
    # A bare string under a list field must not iterate into characters.
    return list(value) if isinstance(value, (list, tuple, set)) else []


def source_values_overridden(person: dict, asserted: dict) -> dict:
    """What the source said, for fields an assertion overrode — only where they differ."""
    published = with_asserted_values(person, asserted)
    return {
        field: person.get(field)
        for field in asserted
        if field in EDITABLE_FIELDS and published.get(field) != person.get(field)
    }


def with_asserted_values(person: dict, asserted: dict) -> dict:
    """`published = (scraped ∪ accepted) − rejected`, per field. A scalar accept replaces
    it; a reject empties it."""
    published = dict(person)
    for field, by_kind in asserted.items():
        if field not in EDITABLE_FIELDS:
            continue
        accepted = by_kind.get(AssertionKind.ACCEPT) or []
        rejected = by_kind.get(AssertionKind.REJECT) or []

        if field in LIST_FIELDS:
            kept = [
                value
                for value in _values_of(person.get(field))
                if value not in rejected
            ]
            published[field] = kept + [
                value
                for value in accepted
                if value not in kept and value not in rejected
            ]
        elif accepted:
            published[field] = accepted[0]
        elif person.get(field) in rejected:
            published[field] = None
    return published


class PersonPatch(BaseModel):
    # id matches an existing person (overlay `fields`) or is new (`fields` is the whole entry).
    id: str
    fields: dict


class PeopleValidationError(Exception):
    def __init__(self, failures: list[dict]):  # [{id, name, field, message}]
        super().__init__(f"{len(failures)} person field(s) failed validation")
        self.failures = failures


# Overlay edits onto base by id; an id absent from edits is a deletion. Nothing is
# re-serialized, so untouched fields keep their exact representation.
def apply_people_patch(base: list[dict], edits: list[PersonPatch]) -> list[dict]:
    base_by_id = {entry["id"]: entry for entry in base}
    result = []
    for edit in edits:
        fields = {key: value for key, value in edit.fields.items() if key not in SERVER_OWNED_FIELDS}
        base_entry = base_by_id.get(edit.id)
        if base_entry is None:
            result.append({"id": edit.id, **fields})
        else:
            result.append({**base_entry, **fields})
    return result


def _field_errors(exc: ValidationError) -> list[dict]:
    # loc[0] is the field key; loc[-1] would be a list index for list fields.
    return [
        {"field": str(e["loc"][0]) if e["loc"] else "", "message": e["msg"]}
        for e in exc.errors()
    ]


def _person_errors(edit: PersonPatch, entry: dict, errors: list[dict]) -> list[dict]:
    return [{"id": edit.id, "name": entry.get("name"), **err} for err in errors]


# Submission-only rule: a scrape reusing one email across pages has no user to alert.
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


# Submission-only: a person published through the editor is unverifiable without a source.
def _missing_source_errors(entry: dict) -> list[dict]:
    if any(str(url).strip() for url in entry.get("source_urls") or []):
        return []
    return [{"field": "source_urls", "message": "At least one source url is required"}]


# Validates each patched person, then writes normalized values back for only the fields
# actually edited, so untouched fields keep their exact base representation.
def validate_and_normalize(patched: list[dict], edits: list[PersonPatch]) -> list[dict]:
    people = []
    failures = []
    for entry, edit in zip(patched, edits):
        try:
            normalized = SubmittedPersonRecord.model_validate(entry).model_dump()
        except ValidationError as exc:
            failures.extend(_person_errors(edit, entry, _field_errors(exc)))
            people.append(entry)
            continue
        # Against the normalized entry, so two spellings of one phone aren't read as two.
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


# Pure: overlay, validate, normalize, order. The caller owns fetching the base and
# writing the result.
def patch_people(base: list[dict], edits: list[PersonPatch]) -> list[dict]:
    patched = validate_and_normalize(apply_people_patch(base, edits), edits)
    return [order_person_fields(person) for person in patched]


def assertions_from_posts(
    person_id: str,
    held: Iterable[str],
    wanted: Iterable[str],
    changeset_id: str | None = None,
) -> list[Assertion]:
    """The posts a person should hold, as claims: a new id accepts, a dropped one rejects.

    `wanted` is the whole set, not a delta, so the caller never has to say which way a move
    went: it is one id arriving and another leaving, and the fold's collapse does the rest.
    Sorted, so two identical edits file identical claims (R6).
    """
    held, wanted = set(held), set(wanted)

    def claim(post_id: str, kind: AssertionKind) -> Assertion:
        return Assertion(
            entity_type=EntityType.PERSON,
            entity_id=person_id,
            field_path=POSTS_FIELD,
            kind=kind,
            value=post_id,
            sources=[Source(note=DefaultNote.EDITED)],
            changeset_id=changeset_id,
        )

    return [
        *(claim(post_id, AssertionKind.ACCEPT) for post_id in sorted(wanted - held)),
        *(claim(post_id, AssertionKind.REJECT) for post_id in sorted(held - wanted)),
    ]


def assertions_from_edit(
    person_id: str, scraped: dict, edited: dict, changeset_id: str | None = None
) -> list[Assertion]:
    """A reviewer's save as assertions, diffed against the scrape so repeat saves stay
    idempotent."""
    urls = [
        url
        for url in (edited.get("source_urls") or scraped.get("source_urls") or [])
        if url
    ]
    sources = [Source(url=urls[0])] if urls else [Source(note=DefaultNote.EDITED)]

    def assertion(field: str, kind: AssertionKind, value: object) -> Assertion:
        return Assertion(
            entity_type=EntityType.PERSON,
            entity_id=person_id,
            field_path=field,
            kind=kind,
            value=value,
            sources=sources,
            changeset_id=changeset_id,
        )

    claims: list[Assertion] = []
    for field in EDITABLE_FIELDS:
        if field in NOT_ASSERTABLE:
            continue
        was, now = scraped.get(field), edited.get(field)
        rejectable = field not in NOT_REJECTABLE

        if field in LIST_FIELDS:
            was, now = set(_values_of(was)), set(_values_of(now))
            claims.extend(
                assertion(field, AssertionKind.ACCEPT, v) for v in sorted(now - was)
            )
            if rejectable:
                claims.extend(
                    assertion(field, AssertionKind.REJECT, v) for v in sorted(was - now)
                )
        elif now not in (None, "") and now != was:
            claims.append(assertion(field, AssertionKind.ACCEPT, now))
        elif was and now in (None, "") and rejectable:
            claims.append(assertion(field, AssertionKind.REJECT, was))

    return claims
