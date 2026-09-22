"""What one field of one person says.

Two policies, one per kind of field, and the table below is the only place that knowledge
lives:

    scalar    the newest claimed value, else the newest a record carries; None if neither

    list      every value a current record carries, plus accepted values; `()` if neither
"""

from collections.abc import Callable, Iterable

from shared.utils.email_utils import is_valid_email, normalize_email
from shared.utils.name_utils import same_name
from shared.utils.phone_utils import normalize_phone_number

from core.projection.facts import Claim, ClaimKind, Facts, SourceRecord, latest_first

NAME = "name"
OTHER_NAMES = "other_names"

SCALAR_FIELDS: dict[str, str] = {
    "name": "name",
    "image": "image",
    "cdn_image": "cdn_image",
}

LIST_FIELDS: dict[str, str] = {
    "phones": "phone",
    "emails": "email",
    "urls": "url",
}


def _valid_email(value: str) -> str | None:
    email = normalize_email(value)
    return email if email and is_valid_email(email) else None


RECORD_NORMALIZERS: dict[str, Callable[[str], str | None]] = {
    "phones": normalize_phone_number,
    "emails": _valid_email,
}


def claims_for(
    members: Iterable[str], field: str, kind: ClaimKind, facts: Facts
) -> list[Claim]:
    """This cluster's live claims of one kind about one field, oldest first."""
    members = set(members)
    return sorted(
        (
            claim
            for claim in facts.claims
            if claim.entity_id in members
            and claim.field_path == field
            and claim.kind == kind
        ),
        key=latest_first,
    )


def records_for(members: Iterable[str], facts: Facts) -> list[SourceRecord]:
    members = set(members)
    return sorted(
        (r for r in facts.records if r.person_id in members), key=latest_first
    )


def current_records(members: Iterable[str], facts: Facts) -> list[SourceRecord]:
    records = records_for(members, facts)
    newest: dict[str, str] = {}
    for record in records:
        newest[record.organization_id] = (
            record.changeset_id
        )  # each org points at newest records

    return [
        record
        for record in records
        if record.changeset_id == newest[record.organization_id]
    ]


def _stands(accepts: list[Claim], rejects: list[Claim]):
    """Whether a value survives what people have said about it."""

    def stands(value) -> bool:
        claims = sorted(
            (k for k in accepts + rejects if k.value == value), key=latest_first
        )
        return not claims or claims[-1].kind != ClaimKind.REJECT

    return stands


def scalar_value(members: Iterable[str], field: str, facts: Facts) -> str | None:
    accepts = claims_for(members, field, ClaimKind.ACCEPT, facts)
    stands = _stands(accepts, claims_for(members, field, ClaimKind.REJECT, facts))
    attribute = SCALAR_FIELDS[field]

    for claim in reversed(accepts):
        if stands(claim.value):
            return claim.value
    for record in reversed(records_for(members, facts)):
        value = getattr(record, attribute)
        if value is not None and stands(value):
            return value
    return None


def list_value(members: Iterable[str], field: str, facts: Facts) -> tuple[str, ...]:
    accepts = claims_for(members, field, ClaimKind.ACCEPT, facts)
    stands = _stands(accepts, claims_for(members, field, ClaimKind.REJECT, facts))
    attribute = LIST_FIELDS[field]

    normalize = RECORD_NORMALIZERS.get(field)
    from_records = []
    for record in current_records(members, facts):
        value = getattr(record, attribute)
        if normalize and value is not None:
            value = normalize(value)
        from_records.append(value)
    from_claims = [claim.value for claim in accepts]

    values = []
    for value in from_records + from_claims:
        if value is None:
            continue
        if not stands(value):
            continue
        if value in values:
            continue
        values.append(value)
    return tuple(values)


def source_urls(members: Iterable[str], facts: Facts) -> tuple[str, ...]:
    return tuple(
        sorted({record.source_url for record in current_records(members, facts)})
    )


def other_names(members: Iterable[str], facts: Facts) -> tuple[str, ...]:
    accepts = claims_for(members, OTHER_NAMES, ClaimKind.ACCEPT, facts)
    rejects = claims_for(members, OTHER_NAMES, ClaimKind.REJECT, facts)
    stands = _stands(accepts, rejects)
    published = scalar_value(members, NAME, facts)

    seen = []
    for record in current_records(members, facts):
        seen.extend([record.name] + list(record.other_names))

    for claim in accepts:
        seen.append(claim.value)

    kept = []
    for name in seen:
        if not name:
            continue
        if published and same_name(name, published):
            continue
        if not stands(name):
            continue
        if any(same_name(name, k) for k in kept):
            continue
        kept.append(name)
    return tuple(sorted(kept))
